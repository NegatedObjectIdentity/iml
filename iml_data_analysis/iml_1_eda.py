# *- coding: utf-8 -*-
'''
Interpretable Machine-Learning - Exploratory Data Analysis (EDA)
v167
@author: Dr. David Steyrl david.steyrl@univie.ac.at
'''

import math as mth
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import seaborn as sns
import shutil
import warnings
from itertools import permutations
from lightgbm import LGBMClassifier
from lightgbm import LGBMRegressor
from scipy.stats import loguniform
from scipy.stats import uniform
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.metrics import balanced_accuracy_score
from sklearn.metrics import r2_score
from sklearn.model_selection import RandomizedSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.preprocessing import TargetEncoder
from sklearn_repeated_group_k_fold import RepeatedGroupKFold


def create_dir(path):
    '''
    Create specified directory if not existing.

    Parameters
    ----------
    path : string
        Path to to check to be created.

    Returns
    -------
    None.
    '''

    # Create dir of not existing ----------------------------------------------
    # Check if dir exists
    if not os.path.isdir(path):
        # Create dir
        os.mkdir(path)

    # Return None -------------------------------------------------------------
    return


def prepare(objective=None):
    '''
    Prepare estimator, prepare seach_space.

    Parameters
    ----------
    objective : string
        String with objective describtion variables.

    Returns
    -------
    estimator : scikit-learn compatible estimator
        Prepared estimator object.
    space : dict
        Space that should be searched for optimale parameters.
    '''

    # Make estimator ----------------------------------------------------------
    # Regression
    if objective == 'regression':
        # Estimator
        estimator = LGBMRegressor(
            boosting_type='gbdt',
            num_leaves=100,
            max_depth=-1,
            learning_rate=0.1,
            n_estimators=100,
            subsample_for_bin=100000,
            objective='huber',
            min_split_gain=0,
            min_child_weight=0.0001,
            min_child_samples=10,
            subsample=1,
            subsample_freq=0,
            colsample_bytree=1,
            reg_alpha=0,
            reg_lambda=0,
            random_state=None,
            n_jobs=1,
            importance_type='gain',
            **{'data_random_seed': None,
               'data_sample_strategy': 'bagging',
               'extra_seed': None,
               'feature_fraction_seed': None,
               'feature_pre_filter': False,
               'force_col_wise': True,
               'min_data_in_bin': 1,
               'use_quantized_grad': True,
               'verbosity': -1,
               })
    # Classification
    elif objective == 'binary' or objective == 'multiclass':
        # Estimator
        estimator = LGBMClassifier(
            boosting_type='gbdt',
            num_leaves=100,
            max_depth=-1,
            learning_rate=0.1,
            n_estimators=100,
            subsample_for_bin=100000,
            objective=objective,
            class_weight='balanced',
            min_split_gain=0,
            min_child_weight=0.0001,
            min_child_samples=10,
            subsample=1,
            subsample_freq=0,
            colsample_bytree=1,
            reg_alpha=0,
            reg_lambda=0,
            random_state=None,
            n_jobs=1,
            importance_type='gain',
            **{'data_random_seed': None,
               'data_sample_strategy': 'bagging',
               'extra_seed': None,
               'feature_fraction_seed': None,
               'feature_pre_filter': False,
               'force_col_wise': True,
               'min_data_in_bin': 1,
               'use_quantized_grad': True,
               'verbosity': -1,
               })
    # Other
    else:
        # Raise error
        raise ValueError('OBJECTIVE not found.')

    # Make search space -------------------------------------------------------
    # Search space
    space = {
        'estimator__colsample_bytree': uniform(0.1, 0.9),
        'estimator__extra_trees': [True, False],
        'estimator__path_smooth': loguniform(1, 100),
        }

    # Return estimator and space ----------------------------------------------
    return estimator, space


def split_data(df, i_trn, i_tst):
    '''
    Split dataframe in training and testing dataframes.

    Parameters
    ----------
    df : dataframe
        Dataframe holding the data to split.
    i_trn : numpy array
        Array with indices of training data.
    i_tst : numpy array
        Array with indices of testing data.

    Returns
    -------
    df_trn : dataframe
        Dataframe holding the training data.
    df_tst : dataframe
         Dataframe holding the testing data.
    '''

    # Split dataframe via index -----------------------------------------------
    # Dataframe is not empty
    if not df.empty:
        # Make split
        df_trn = df.iloc[i_trn].reset_index(drop=True)
        # Make split
        df_tst = df.iloc[i_tst].reset_index(drop=True)
    # Dataframe is empty
    else:
        # Make empty dataframes
        df_trn, df_tst = pd.DataFrame(), pd.DataFrame()

    # Return train test dataframes --------------------------------------------
    return df_trn, df_tst


def compute_redundancy(task=None, g=None, x=None, y=None, objective=None):
    '''
    Compute redundancy score (R²) of between x and y.

    Parameters
    ----------
    task : dictionary
        Dictionary holding the task describtion variables.
    g : series
        Series holding the group data.
    x : series
        Series holding the predictor data.
    y : series
        Series holding the target data.
    objective : string
        String with objective describtion variables.

    Returns
    -------
    redundacy : float
        Redundancy score (0-1). R² for regression, adjusted balanced accuracy
        for classification.
    '''

    # Initialize results lists ------------------------------------------------
    # Initialize score list
    scores = []
    # Get estimator and space
    estimator, space = prepare(objective)

    # Main cross-validation loop ----------------------------------------------
    # Calculate number of repetition for outer CV
    task['n_rep_outer_cv'] = mth.ceil(task['N_PRED_OUTER_CV']/g.shape[0])
    # Instatiate main cv splitter with fixed random state for comparison
    cv = RepeatedGroupKFold(
        n_splits=task['N_CV_FOLDS'],
        n_repeats=task['n_rep_outer_cv'],
        random_state=None)
    # Loop over main (outer) cross validation splits
    for i_cv, (i_trn, i_tst) in enumerate(cv.split(g, groups=g)):

        # Split data ----------------------------------------------------------
        # Split groups
        g_trn, g_tst = split_data(g, i_trn, i_tst)
        # Split targets
        y_trn, y_tst = split_data(y, i_trn, i_tst)
        # Split predictors
        x_trn, x_tst = split_data(x, i_trn, i_tst)

        # Get scorer ----------------------------------------------------------
        # Regression
        if objective == 'regression':
            # R² score
            scorer = 'r2'
        # Classification
        elif objective == 'binary' or objective == 'multiclass':
            # Balanced accuracy for classification
            scorer = 'balanced_accuracy'
        # Other
        else:
            # Raise error
            raise ValueError('OBJECTIVE not found.')

        # Tune analysis pipeline ----------------------------------------------
        # Choose n_repeats to approx N_SAMPLES_INNER_CV predictions
        task['n_rep_inner_cv'] = mth.ceil(
            task['N_PRED_INNER_CV'] / g_trn.shape[0])
        # Instatiate random parameter search
        search = RandomizedSearchCV(
            estimator,
            space,
            n_iter=task['N_SAMPLES_RS'],
            scoring=scorer,
            n_jobs=task['N_JOBS'],
            refit=True,
            cv=RepeatedGroupKFold(n_splits=task['N_CV_FOLDS'],
                                  n_repeats=task['n_rep_inner_cv'],
                                  random_state=None),
            verbose=0,
            pre_dispatch='2*n_jobs',
            random_state=None,
            error_score=0,
            return_train_score=False)
        # Random search for best parameter
        search.fit(x_trn, y_trn.squeeze(), groups=g_trn)

        # Predict -------------------------------------------------------------
        # Predict test samples
        y_pred = search.best_estimator_.predict(x_tst)

        # Score results -------------------------------------------------------
        # Regression
        if objective == 'regression':
            # Score predictions in terms of R²
            scores.append(r2_score(y_tst, y_pred))
        # Classification
        elif objective == 'binary' or objective == 'multiclass':
            # Calculate model fit in terms of acc
            scores.append(balanced_accuracy_score(
                y_tst, y_pred, adjusted=True))
        # Other
        else:
            # Raise error
            raise ValueError('OBJECTIVE not found.')

    # Process scores ----------------------------------------------------------
    # Limit redundancy score to be bigger than or equal to 0
    redundancy = max(0, np.mean(scores))

    # Return redundancy -------------------------------------------------------
    return redundancy


def eda(task, g, x, y):
    '''
    Carries out exploratory data analysis, incl.:
    1D data distribuation (violinplot),
    2D data distribution (pairplots),
    data correlation (heatmap),
    data linear dimensions (via PCA),
    redundancy of predictors (via LightGBM prediction accuracy),
    outlier in data (via isolation Forests).

    Parameters
    ----------
    task : dictionary
        Dictionary holding the task describtion variables.
    g : dataframe
        Dataframe holding the group data.
    x : dataframe
        Dataframe holding the predictor data.
    y : dataframe
        Dataframe holding the target data.

    Returns
    -------
    None.
    '''

    # Preprocessing -----------------------------------------------------------
    # Instatiate target encoder
    te = TargetEncoder(
        categories='auto',
        target_type='continuous',
        smooth='auto',
        cv=task['N_CV_FOLDS'],
        shuffle=True,
        random_state=None)
    # Get categorical predictors for target-encoder
    coltrans = ColumnTransformer(
        [('con_pred', 'passthrough', task['X_CON_NAMES']),
         ('bin_pred', 'passthrough', task['X_CAT_BIN_NAMES']),
         ('mult_pred', te, task['X_CAT_MULT_NAMES']),
         ('target', 'passthrough', task['y_name']),
         ],
        remainder='drop',
        sparse_threshold=0,
        n_jobs=1,
        transformer_weights=None,
        verbose=False,
        verbose_feature_names_out=False)
    # Pipeline
    pre_pipe = Pipeline(
        [('coltrans', coltrans),
         ('std_scaler', StandardScaler())],
        memory=None,
        verbose=False).set_output(transform='pandas')
    # Concatinate predictors and targets
    z = pd.concat([x, y], axis=1)
    # Do preprocessing
    z = pre_pipe.fit_transform(z, y.squeeze())

    # 1D data distributions ---------------------------------------------------
    # Do 1D data distribution plot?
    if task['DATA_DISTRIBUTION_1D']:
        # x names lengths
        x_names_max_len = max([len(i) for i in task['x_names']])
        # x names count
        x_names_count = len(task['x_names'])
        # Create a figure
        fig, ax = plt.subplots(
            figsize=(x_names_max_len*.1+4, x_names_count*.7+1))
        # Violinplot all data
        sns.violinplot(
            data=z,
            bw_method='scott',
            bw_adjust=0.5,
            cut=2,
            density_norm='width',
            gridsize=100,
            width=0.8,
            inner='box',
            orient='h',
            linewidth=1,
            color='#777777',
            saturation=1.0,
            ax=ax)
        # Remove top, right and left frame elements
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        # Set x ticks and size
        ax.set_xlabel('standardized range', fontsize=10)
        # Set y ticks and size
        ax.set_ylabel(ax.get_ylabel(), fontsize=10)
        # Add horizontal grid
        fig.axes[0].set_axisbelow(True)
        # Set grid style
        fig.axes[0].grid(
            axis='y',
            color='#bbbbbb',
            linestyle='dotted',
            alpha=.3)
        # Make title string
        title_str = (task['ANALYSIS_NAME']+'\n' +
                     '1D data distributions (violin plot)\n')
        # set title
        plt.title(title_str, fontsize=10)

        # Save figure ---------------------------------------------------------
        # Make save path
        save_path = (
            task['path_to_results']+'/'+task['ANALYSIS_NAME'] +
            '_'+task['y_name'][0]+'_eda_1_1d_distribuation')
        # Save figure in .png format
        plt.savefig(save_path+'.png', dpi=300, bbox_inches='tight')
        # Check if save as svg is enabled
        if task['AS_SVG']:
            # Save figure in .svg format
            plt.savefig(save_path+'.svg', bbox_inches='tight')
        # Show plot
        plt.show()

    # 2D data distribution ----------------------------------------------------
    # Do 2D data distribution plot?
    if task['DATA_DISTRIBUTION_2D']:
        # Make pairplot
        pair_plot = sns.pairplot(
            z,
            corner=False,
            diag_kind='kde',
            plot_kws={'color': '#777777'},
            diag_kws={'color': '#777777'})
        # Make title string
        title_str = (task['ANALYSIS_NAME']+'\n' +
                     '2D data distributions (pair plot)\n')
        # set title
        pair_plot.fig.suptitle(title_str, fontsize=10, y=1.0)
        # Add variable kde to plot
        pair_plot.map_lower(sns.kdeplot, levels=3, color='.2')

        # Save figure ---------------------------------------------------------
        # Make save path
        save_path = (
            task['path_to_results']+'/'+task['ANALYSIS_NAME'] +
            '_'+task['y_name'][0]+'_eda_2_2d_distribution')
        # Save figure in .png format
        plt.savefig(save_path+'.png', dpi=300, bbox_inches='tight')
        # Check if save as svg is enabled
        if task['AS_SVG']:
            # Save figure in .svg format
            plt.savefig(save_path+'.svg', bbox_inches='tight')
        # Show plot
        plt.show()

    # Correlations ------------------------------------------------------------
    # Do correlation heatmap plot?
    if task['DATA_CORRELATIONS']:
        # x names lengths
        x_names_max_len = max([len(i) for i in task['x_names']])
        # x names count
        x_names_count = len(task['x_names'])
        # Create a figure
        fig, ax = plt.subplots(
            figsize=(x_names_count*.6+x_names_max_len*.1+1,
                     x_names_count*.6+x_names_max_len*.1+1))
        # Make colorbar string
        clb_str = ('correlation (-1 to 1)')
        # Print correlations
        sns.heatmap(
            z.corr(),
            vmin=-1,
            vmax=1,
            cmap='Greys',
            center=None,
            robust=True,
            annot=True,
            fmt='.2f',
            annot_kws={'size': 10},
            linewidths=.5,
            linecolor='#999999',
            cbar=True,
            cbar_kws={'label': clb_str, 'shrink': 0.6},
            cbar_ax=None,
            square=True,
            xticklabels=1,
            yticklabels=1,
            mask=None,
            ax=ax)
        # This sets the yticks 'upright' with 0, as opposed to sideways with 90
        plt.yticks(rotation=0)
        # This sets the xticks 'sideways' with 90
        plt.xticks(rotation=90)
        # Make title string
        title_str = (task['ANALYSIS_NAME']+'\n' +
                     'Linear correlation coefficients (heatmap)\n')
        # set title
        plt.title(title_str, fontsize=10)
        # Get colorbar
        cb_ax = fig.axes[1]
        # Modifying color bar tick size
        cb_ax.tick_params(labelsize=10)
        # Modifying color bar fontsize
        cb_ax.set_ylabel(clb_str, fontsize=10)
        cb_ax.set_box_aspect(50)

        # Save figure ---------------------------------------------------------
        # Make save path
        save_path = (
            task['path_to_results']+'/'+task['ANALYSIS_NAME'] +
            '_'+task['y_name'][0]+'_eda_3_correlations')
        # Save figure in .png format
        plt.savefig(save_path+'.png', dpi=300, bbox_inches='tight')
        # Check if save as svg is enabled
        if task['AS_SVG']:
            # Save figure in .svg format
            plt.savefig(save_path+'.svg', bbox_inches='tight')
        # Show plot
        plt.show()

    # Linear dimensions analysis with PCA -------------------------------------
    # Do linear dimensions analysis?
    if task['DATA_LINEAR_DIMENSIONS']:
        # Check for NaN values
        if not z.isnull().values.any():
            # Instanciate PCA
            pca = PCA(
                n_components=x.shape[1],
                copy=True,
                whiten=False,
                svd_solver='auto',
                tol=0.0001,
                iterated_power='auto',
                random_state=None)
            # Fit PCA
            pca.fit(x)
            # x names count
            x_names_count = len(task['x_names'])
            # Make figure
            fig, ax = plt.subplots(figsize=(min((1+x_names_count*.6), 16), 4))
            # Plot data
            ax.plot(
                pca.explained_variance_ratio_,
                label='Explained variance per component')
            # Add dots
            ax.plot(
                pca.explained_variance_ratio_,
                color='black',
                marker='.',
                linestyle='None')
            # Set x limit
            ax.set_xlim((-0.01, ax.get_xlim()[1]))
            # Set y limit
            ax.set_ylim((-0.01, 1.01))
            # Remove top, right and left frame elements
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            # Add x label
            ax.set_xlabel('PCA-component')
            # Add y label
            ax.set_ylabel('Explained Variance')
            # Create twin x axis
            ax2 = ax.twinx()
            # Plot cum sum of explained variance
            ax2.plot(
                np.cumsum(pca.explained_variance_ratio_),
                color='orange',
                label='Cumulative explained variance')
            # Add dots
            ax2.plot(
                np.cumsum(pca.explained_variance_ratio_),
                color='black',
                marker='.',
                linestyle='None')
            # Set x limit
            ax2.set_xlim((-0.01, ax2.get_xlim()[1]))
            # Set y limit
            ax2.set_ylim((-0.01, 1.01))
            # Remove top, right and left frame elements
            ax2.spines['top'].set_visible(False)
            ax2.spines['left'].set_visible(False)
            # Add y label
            ax2.set_ylabel('Cumulative Variance')
            # Add labels to ax
            for comp, t in enumerate(
                    pca.explained_variance_ratio_.round(decimals=2)):
                # Add current label
                ax.text(comp, t, t, fontsize=10)
            # Add cum sum labels
            for comp, t in enumerate(
                    np.cumsum(
                        pca.explained_variance_ratio_).round(decimals=2)):
                # Add current cumsum label
                ax2.text(comp, t, t, fontsize=10)
            # Add legend
            fig.legend(
                loc='center right',
                bbox_to_anchor=(1, 0.5),
                bbox_transform=ax.transAxes)
            # Make title string
            title_str = (
                task['ANALYSIS_NAME']+'\n' +
                'Linear dimensions via PCA\n')
            # set title
            plt.title(title_str, fontsize=10)

            # Save figure -----------------------------------------------------
            # Make save path
            save_path = (
                task['path_to_results']+'/'+task['ANALYSIS_NAME'] +
                '_'+task['y_name'][0]+'_eda_4_data_linear_dim')
            # Save figure in .png format
            plt.savefig(save_path+'.png', dpi=300, bbox_inches='tight')
            # Check if save as svg is enabled
            if task['AS_SVG']:
                # Save figure in .svg format
                plt.savefig(save_path+'.svg', bbox_inches='tight')
            # show figure
            plt.show()
        # If nans
        else:
            # Raise warning
            warnings.warn('PCA skipped because of NaN values.')

    # Data redundancy via LigthGBM --------------------------------------------
    # Do data redundancy analysis?
    if task['DATA_REDUNDANCY']:
        # Make redundancy matrix
        redundancy = np.ones((len(list(z.columns)), len(list(z.columns))))
        # Make pairs
        for (id_pred1, id_pred2) in permutations(pd.factorize(
                pd.Series(z.columns))[0], 2):
            # Make a mapping list between number and name
            mapping = list(z.columns)
            # Select task continous prediction target
            if mapping[id_pred2] in task['X_CON_NAMES']:
                # Select objective
                objective = 'regression'
                # Get predictor data
                xt = pd.DataFrame(z[mapping[id_pred1]])
                # Get target data
                yt = pd.DataFrame(z[mapping[id_pred2]])
            # Select task binary prediction target
            elif mapping[id_pred2] in task['X_CAT_BIN_NAMES']:
                # Select objective
                objective = 'binary'
                # Get predictor data
                xt = pd.DataFrame(z[mapping[id_pred1]])
                # Get target data
                yt = pd.DataFrame(pd.factorize(z[mapping[id_pred2]])[0],
                                  columns=[mapping[id_pred2]])
            # Select task multi class prediction target trat as regression
            elif mapping[id_pred2] in task['X_CAT_MULT_NAMES']:
                # Select objective
                objective = 'regression'
                # Get predictor data
                xt = pd.DataFrame(z[mapping[id_pred1]])
                # Get target data
                yt = pd.DataFrame(z[mapping[id_pred2]])
            # Select task target objective
            elif mapping[id_pred2] in task['Y_NAMES']:
                # Select objective
                objective = task['OBJECTIVE']
                # Get predictor data
                xt = pd.DataFrame(z[mapping[id_pred1]])
                # Get target data select by objective regression
                if objective == 'regression':
                    # Get target data
                    yt = pd.DataFrame(z[mapping[id_pred2]])
                # Get target data select by objective other than regression
                else:
                    # Get target data
                    yt = pd.DataFrame(pd.factorize(z[mapping[id_pred2]])[0],
                                      columns=[mapping[id_pred2]])
            # Other target objective
            else:
                # Raise error
                raise ValueError('OBJECTIVE not found.')
            # Compute redundancy of current pair
            redundancy[id_pred1, id_pred2] = compute_redundancy(
                task=task, g=g, x=xt, y=yt, objective=objective)
        # Names lengths
        names_max_len = max([len(i) for i in list(z.columns)])
        # Names count
        names_count = len(list(z.columns))
        # Create a figure
        fig, ax = plt.subplots(
            figsize=(names_count*.6+names_max_len*.1+1,
                     names_count*.6+names_max_len*.1+1))
        # Make colorbar string
        clb_str = ('redundancy (0 to 1)')
        # Print redundancy
        sns.heatmap(
            redundancy,
            vmin=0,
            vmax=1,
            cmap='Greys',
            center=None,
            robust=True,
            annot=True,
            fmt='.2f',
            annot_kws={'size': 10},
            linewidths=.5,
            linecolor='#999999',
            cbar=True,
            cbar_kws={'label': clb_str, 'shrink': 0.6},
            cbar_ax=None,
            square=True,
            xticklabels=list(z.columns),
            yticklabels=list(z.columns),
            mask=None,
            ax=ax)
        # Make title string
        title_str = (task['ANALYSIS_NAME']+'\n' +
                     'Non-linear redundancy via ' +
                     'pairwise predictions (heatmap)\n' +
                     'y-axis: predictors, x-axis: prediction targets\n')
        # set title
        plt.title(title_str, fontsize=10)

        # Save figure -----------------------------------------------------
        # Make save path
        save_path = (
            task['path_to_results']+'/'+task['ANALYSIS_NAME'] +
            '_'+task['y_name'][0]+'_eda_5_redundancy')
        # Save figure in .png format
        plt.savefig(save_path+'.png', dpi=300, bbox_inches='tight')
        # Check if save as svg is enabled
        if task['AS_SVG']:
            # Save figure in .svg format
            plt.savefig(save_path+'.svg', bbox_inches='tight')
        # show figure
        plt.show()

    # Outlier dection via Isolation Forests -----------------------------------
    # Do outlier detection in data?
    if task['DATA_OUTLIER']:
        # Check for NaN values
        if not z.isnull().values.any():
            # Instanciate isolation forest
            iForest = IsolationForest(
                n_estimators=10000,
                max_samples='auto',
                contamination='auto',
                max_features=1.0,
                bootstrap=False,
                n_jobs=-2,
                random_state=None,
                verbose=0,
                warm_start=False)
            # Fit data and predict outlier
            outlier = iForest.fit_predict(x)
            # Make outlier dataframe
            outlier_df = pd.DataFrame(data=outlier, columns=['is_outlier'])
            # Outlier score
            outlier_score = iForest.decision_function(x)
            # Make figure
            fig, ax = plt.subplots(figsize=(8, 5))
            # Plot hist of inlier score
            sns.histplot(
                data=outlier_score,
                bins=30,
                kde=True,
                color='#777777',
                ax=ax)
            # Remove top, right and left frame elements
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            # Add x label
            ax.set_xlabel('Isolation Forest outlier score')
            # Add y label
            ax.set_ylabel('Count')
            # Create title string
            title_str = (
                task['ANALYSIS_NAME']+'\n' +
                'Outlier detection via Isolation Forest: ' +
                '{:.1f}% potential outliers\n')
            # Add title
            ax.set_title(
                title_str.format(np.sum(outlier == -1)/len(outlier)*100))

            # Save figure -----------------------------------------------------
            # Make save path
            save_path = (
                task['path_to_results']+'/'+task['ANALYSIS_NAME'] +
                '_'+task['y_name'][0]+'_eda_6_outlier')
            # Save outlier data
            outlier_df.to_excel(save_path+'.xlsx')
            # Save figure in .png format
            plt.savefig(save_path+'.png', dpi=300, bbox_inches='tight')
            # Check if save as svg is enabled
            if task['AS_SVG']:
                # Save figure in .svg format
                plt.savefig(save_path+'.svg', bbox_inches='tight')
            # show figure
            plt.show()
        # If nans
        else:
            # Raise warning
            warnings.warn('Warning: Outlier skipped because of NaN values.')

    # Return ------------------------------------------------------------------
    return


def main():
    '''
    Main function of exploratory data analysis.

    Returns
    -------
    None.
    '''

    ###########################################################################
    # Specify analysis task
    ###########################################################################

    # 1. Specify task ---------------------------------------------------------
    # Specify max number of samples. int (default: 10000)
    MAX_SAMPLES = 10000
    # Do 1D data distribution violon plot in EDA? bool (default: True)
    DATA_DISTRIBUTION_1D = True
    # Do 2D data distribution pair plot in EDA? bool (default: True)
    DATA_DISTRIBUTION_2D = True
    # Do data correlation heatmap in EDA? bool (default: True)
    DATA_CORRELATIONS = True
    # Do linear dimensions analysis with PCA in EDA? bool (default: True)
    DATA_LINEAR_DIMENSIONS = True
    # Do data redundancy analysis in EDA? (default: True)
    DATA_REDUNDANCY = True
    # Use Isolation Forest to detect outliers in EDA? bool (default: True)
    DATA_OUTLIER = True
    # Number parallel processing jobs. int (-1=all, -2=all-1)
    N_JOBS = -2
    # Number of folds in CV. int (default: 5)
    N_CV_FOLDS = 5
    # Number of predictions in outer CV. int (default: 10000)
    N_PRED_OUTER_CV = 10000
    # Number of tries in random search. int (default: 100)
    N_SAMPLES_RS = 100
    # Number of predictions in inner CV. int (default: 1000)
    N_PRED_INNER_CV = 1000
    # Save plots additionally AS_SVG? bool (default: False)
    AS_SVG = False

    # 2. Specify data ---------------------------------------------------------

    # # Cancer data - classification 2 class, unbalanced classes
    # # Specifiy an analysis name
    # ANALYSIS_NAME = 'cancer'
    # # Specify path to data. string
    # PATH_TO_DATA = 'data/cancer_20230927.xlsx'
    # # Specify sheet name. string
    # SHEET_NAME = 'data'
    # # Specify task OBJECTIVE. string (regression, binary, multiclass)
    # OBJECTIVE = 'binary'
    # # Specify grouping for CV split. list of string
    # G_NAME = [
    #     'sample_id',
    #     ]
    # # Specify continous predictor names. list of string or []
    # X_CON_NAMES = [
    #     'mean_radius',
    #     'mean_texture',
    #     'mean_perimeter',
    #     'mean_area',
    #     'mean_smoothness',
    #     'mean_compactness',
    #     'mean_concavity',
    #     'mean_concave_points',
    #     'mean_symmetry',
    #     'mean_fractal_dimension',
    #     'radius_error',
    #     'texture_error',
    #     'perimeter_error',
    #     'area_error',
    #     'smoothness_error',
    #     'compactness_error',
    #     'concavity_error',
    #     'concave_points_error',
    #     'symmetry_error',
    #     'fractal_dimension_error',
    #     'worst_radius',
    #     'worst_texture',
    #     'worst_perimeter',
    #     'worst_area',
    #     'worst_smoothness',
    #     'worst_compactness',
    #     'worst_concavity',
    #     'worst_concave_points',
    #     'worst_symmetry',
    #     'worst_fractal_dimension',
    #     ]
    # # Specify binary categorical predictor names. list of string or []
    # X_CAT_BIN_NAMES = []
    # # Specify multi categorical predictor names. list of string or []
    # X_CAT_MULT_NAMES = []
    # # Specify target name(s). list of strings or []
    # Y_NAMES = [
    #     'target',
    #     ]
    # # Rows to skip. list of int or []
    # SKIP_ROWS = []

    # # Covid data - classification 2 class
    # # Specifiy an analysis name
    # ANALYSIS_NAME = 'covid'
    # # Specify path to data. string
    # PATH_TO_DATA = 'data/covid_20240221.xlsx'
    # # Specify sheet name. string
    # SHEET_NAME = 'data'
    # # Specify task OBJECTIVE. string (regression, binary, multiclass)
    # OBJECTIVE = 'binary'
    # # Specify grouping for CV split. list of string
    # G_NAME = [
    #     'sample_id',
    #     ]
    # # Specify continous predictor names. list of string or []
    # X_CON_NAMES = []
    # # Specify binary categorical predictor names. list of string or []
    # X_CAT_BIN_NAMES = [
    #     'age_over_50',
    #     'vaccinated',
    #     ]
    # # Specify multi categorical predictor names. list of string or []
    # X_CAT_MULT_NAMES = []
    # # Specify target name(s). list of strings or []
    # Y_NAMES = [
    #     'survived',
    #     ]
    # # Rows to skip. list of int or []
    # SKIP_ROWS = []

    # Diabetes data - regression, binary category predictor
    # Specifiy an analysis name
    ANALYSIS_NAME = 'diabetes'
    # Specify path to data. string
    PATH_TO_DATA = 'data/diabetes_20230809.xlsx'
    # Specify sheet name. string
    SHEET_NAME = 'data'
    # Specify task OBJECTIVE. string (regression, binary, multiclass)
    OBJECTIVE = 'regression'
    # Specify grouping for CV split. list of string
    G_NAME = [
        'sample_id',
        ]
    # Specify continous predictor names. list of string or []
    X_CON_NAMES = [
        'age',
        'bmi',
        'bp',
        's1',
        's2',
        's3',
        's4',
        's5',
        's6',
        ]
    # Specify binary categorical predictor names. list of string or []
    X_CAT_BIN_NAMES = [
        'sex',
        ]
    # Specify multi categorical predictor names. list of string or []
    X_CAT_MULT_NAMES = []
    # Specify target name(s). list of strings or []
    Y_NAMES = [
        'progression',
        ]
    # Rows to skip. list of int or []
    SKIP_ROWS = []

    # # Diabetes data - regression, binary category predictor
    # # Specifiy an analysis name
    # ANALYSIS_NAME = 'diabetes_singlepred'
    # # Specify path to data. string
    # PATH_TO_DATA = 'data/diabetes_20230809.xlsx'
    # # Specify sheet name. string
    # SHEET_NAME = 'data'
    # # Specify task OBJECTIVE. string (regression, binary, multiclass)
    # OBJECTIVE = 'regression'
    # # Specify grouping for CV split. list of string
    # G_NAME = [
    #     'sample_id',
    #     ]
    # # Specify continous predictor names. list of string or []
    # X_CON_NAMES = [
    #     'bmi',
    #     ]
    # # Specify binary categorical predictor names. list of string or []
    # X_CAT_BIN_NAMES = []
    # # Specify multi categorical predictor names. list of string or []
    # X_CAT_MULT_NAMES = []
    # # Specify target name(s). list of strings or []
    # Y_NAMES = [
    #     'progression',
    #     ]
    # # Rows to skip. list of int or []
    # SKIP_ROWS = []

    # # Digits data - classification 10 class, multicategory predictors
    # # Specifiy an analysis name
    # ANALYSIS_NAME = 'digits'
    # # Specify path to data. string
    # PATH_TO_DATA = 'data/digit_20230809.xlsx'
    # # Specify sheet name. string
    # SHEET_NAME = 'data'
    # # Specify task OBJECTIVE. string (regression, binary, multiclass)
    # OBJECTIVE = 'multiclass'
    # # Specify grouping for CV split. list of string
    # G_NAME = [
    #     'sample_id',
    #     ]
    # # Specify continous predictor names. list of string or []
    # X_CON_NAMES = []
    # # Specify binary categorical predictor names. list of string or []
    # X_CAT_BIN_NAMES = []
    # # Specify multi categorical predictor names. list of string or []
    # X_CAT_MULT_NAMES = [
    #     'pixel_0_1',
    #     'pixel_0_2',
    #     'pixel_0_3',
    #     'pixel_0_4',
    #     'pixel_0_5',
    #     'pixel_0_6',
    #     'pixel_0_7',
    #     'pixel_1_0',
    #     'pixel_1_1',
    #     'pixel_1_2',
    #     'pixel_1_3',
    #     'pixel_1_4',
    #     'pixel_1_5',
    #     'pixel_1_6',
    #     'pixel_1_7',
    #     'pixel_2_0',
    #     'pixel_2_1',
    #     'pixel_2_2',
    #     'pixel_2_3',
    #     'pixel_2_4',
    #     'pixel_2_5',
    #     'pixel_2_6',
    #     'pixel_2_7',
    #     'pixel_3_0',
    #     'pixel_3_1',
    #     'pixel_3_2',
    #     'pixel_3_3',
    #     'pixel_3_4',
    #     'pixel_3_5',
    #     'pixel_3_6',
    #     'pixel_3_7',
    #     'pixel_4_0',
    #     'pixel_4_1',
    #     'pixel_4_2',
    #     'pixel_4_3',
    #     'pixel_4_4',
    #     'pixel_4_5',
    #     'pixel_4_6',
    #     'pixel_4_7',
    #     'pixel_5_0',
    #     'pixel_5_1',
    #     'pixel_5_2',
    #     'pixel_5_3',
    #     'pixel_5_4',
    #     'pixel_5_5',
    #     'pixel_5_6',
    #     'pixel_5_7',
    #     'pixel_6_0',
    #     'pixel_6_1',
    #     'pixel_6_2',
    #     'pixel_6_3',
    #     'pixel_6_4',
    #     'pixel_6_5',
    #     'pixel_6_6',
    #     'pixel_6_7',
    #     'pixel_7_0',
    #     'pixel_7_1',
    #     'pixel_7_2',
    #     'pixel_7_3',
    #     'pixel_7_4',
    #     'pixel_7_5',
    #     'pixel_7_6',
    #     'pixel_7_7',
    #     ]
    # # Specify target name(s). list of strings or []
    # Y_NAMES = [
    #     'digit',
    #     ]
    # # Rows to skip. list of int or []
    # SKIP_ROWS = []

    # # Housing data - regression, multicategory predictor
    # # Specifiy an analysis name
    # ANALYSIS_NAME = 'housing'
    # # Specify path to data. string
    # PATH_TO_DATA = 'data/housing_20230907.xlsx'
    # # Specify sheet name. string
    # SHEET_NAME = 'data'
    # # Specify task OBJECTIVE. string (regression, binary, multiclass)
    # OBJECTIVE = 'regression'
    # # Specify grouping for CV split. list of string
    # G_NAME = [
    #     'sample_id',
    #     ]
    # # Specify continous predictor names. list of string or []
    # X_CON_NAMES = [
    #     'median_income',
    #     'house_age',
    #     'average_rooms',
    #     'average_bedrooms',
    #     'population',
    #     'average_occupation',
    #     'latitude',
    #     'longitude',
    #     ]
    # # Specify binary categorical predictor names. list of string or []
    # X_CAT_BIN_NAMES = []
    # # Specify multi categorical predictor names. list of string or []
    # X_CAT_MULT_NAMES = [
    #     'ocean_proximity',
    #     ]
    # # Specify target name(s). list of strings or []
    # Y_NAMES = [
    #     'median_house_value',
    #     ]
    # # Rows to skip. list of int or []
    # SKIP_ROWS = []

    # # Iris data - classification 2 class,
    # # Specifiy an analysis name
    # ANALYSIS_NAME = 'iris_2'
    # # Specify path to data. string
    # PATH_TO_DATA = 'data/iris_20230809.xlsx'
    # # Specify sheet name. string
    # SHEET_NAME = 'data_2class'
    # # Specify task OBJECTIVE. string (regression, binary, multiclass)
    # OBJECTIVE = 'binary'
    # # Specify grouping for CV split. list of string
    # G_NAME = [
    #     'sample_id',
    #     ]
    # # Specify continous predictor names. list of string or []
    # X_CON_NAMES = [
    #     'sepal_length',
    #     'sepal_width',
    #     'petal_length',
    #     'petal_width',
    #     ]
    # # Specify binary categorical predictor names. list of string or []
    # X_CAT_BIN_NAMES = []
    # # Specify multi categorical predictor names. list of string or []
    # X_CAT_MULT_NAMES = []
    # # Specify target name(s). list of strings or []
    # Y_NAMES = [
    #     'type',
    #     ]
    # # Rows to skip. list of int or []
    # SKIP_ROWS = []

    # # Iris data - classification 3 class,
    # # Specifiy an analysis name
    # ANALYSIS_NAME = 'iris_3'
    # # Specify path to data. string
    # PATH_TO_DATA = 'data/iris_20230809.xlsx'
    # # Specify sheet name. string
    # SHEET_NAME = 'data_3class'
    # # Specify task OBJECTIVE. string (regression, binary, multiclass)
    # OBJECTIVE = 'multiclass'
    # # Specify grouping for CV split. list of string
    # G_NAME = [
    #     'sample_id',
    #     ]
    # # Specify continous predictor names. list of string or []
    # X_CON_NAMES = [
    #     'sepal_length',
    #     'sepal_width',
    #     'petal_length',
    #     'petal_width',
    #     ]
    # # Specify binary categorical predictor names. list of string or []
    # X_CAT_BIN_NAMES = []
    # # Specify multi categorical predictor names. list of string or []
    # X_CAT_MULT_NAMES = []
    # # Specify target name(s). list of strings or []
    # Y_NAMES = [
    #     'type',
    #     ]
    # # Rows to skip. list of int or []
    # SKIP_ROWS = []

    # # Radon data - regression, binary and multicategory predictors
    # # Specifiy an analysis name
    # ANALYSIS_NAME = 'radon'
    # # Specify path to data. string
    # PATH_TO_DATA = 'data/radon_20230809.xlsx'
    # # Specify sheet name. string
    # SHEET_NAME = 'data'
    # # Specify task OBJECTIVE. string (regression, binary, multiclass)
    # OBJECTIVE = 'regression'
    # # Specify grouping for CV split. list of string
    # G_NAME = [
    #     'sample_id',
    #     ]
    # # Specify continous predictor names. list of string or []
    # X_CON_NAMES = [
    #     'Uppm',
    #     ]
    # # Specify binary categorical predictor names. list of string or []
    # X_CAT_BIN_NAMES = [
    #     'basement',
    #     'floor',
    #     ]
    # # Specify multi categorical predictor names. list of string or []
    # X_CAT_MULT_NAMES = [
    #     'county_code',
    #     ]
    # # Specify target name(s). list of strings or []
    # Y_NAMES = [
    #     'log_radon',
    #     ]
    # # Rows to skip. list of int or []
    # SKIP_ROWS = []

    ###########################################################################

    # Create results directory path -------------------------------------------
    path_to_results = 'res_eda_'+ANALYSIS_NAME

    # Create task variable ----------------------------------------------------
    task = {
        'MAX_SAMPLES': MAX_SAMPLES,
        'N_JOBS': N_JOBS,
        'N_CV_FOLDS': N_CV_FOLDS,
        'DATA_DISTRIBUTION_1D': DATA_DISTRIBUTION_1D,
        'DATA_DISTRIBUTION_2D': DATA_DISTRIBUTION_2D,
        'DATA_CORRELATIONS': DATA_CORRELATIONS,
        'DATA_LINEAR_DIMENSIONS': DATA_LINEAR_DIMENSIONS,
        'DATA_REDUNDANCY': DATA_REDUNDANCY,
        'N_PRED_OUTER_CV': N_PRED_OUTER_CV,
        'N_PRED_INNER_CV': N_PRED_INNER_CV,
        'N_SAMPLES_RS': N_SAMPLES_RS,
        'DATA_OUTLIER': DATA_OUTLIER,
        'AS_SVG': AS_SVG,
        'ANALYSIS_NAME': ANALYSIS_NAME,
        'PATH_TO_DATA': PATH_TO_DATA,
        'SHEET_NAME': SHEET_NAME,
        'OBJECTIVE': OBJECTIVE,
        'G_NAME': G_NAME,
        'X_CON_NAMES': X_CON_NAMES,
        'X_CAT_BIN_NAMES': X_CAT_BIN_NAMES,
        'X_CAT_MULT_NAMES': X_CAT_MULT_NAMES,
        'Y_NAMES': Y_NAMES,
        'SKIP_ROWS': SKIP_ROWS,
        'path_to_results': path_to_results,
        'x_names': X_CON_NAMES+X_CAT_BIN_NAMES+X_CAT_MULT_NAMES,
        }

    # Create results directory ------------------------------------------------
    create_dir(path_to_results)

    # Copy this python script to results directory ----------------------------
    shutil.copy('iml_1_eda.py', path_to_results+'/iml_1_eda.py')

    # Load data ---------------------------------------------------------------
    # Load groups from excel file
    G = pd.read_excel(
        task['PATH_TO_DATA'],
        sheet_name=task['SHEET_NAME'],
        header=0,
        usecols=task['G_NAME'],
        dtype=np.float64,
        skiprows=task['SKIP_ROWS'])
    # Load predictors from excel file
    X = pd.read_excel(
        task['PATH_TO_DATA'],
        sheet_name=task['SHEET_NAME'],
        header=0,
        usecols=task['x_names'],
        dtype=np.float64,
        skiprows=task['SKIP_ROWS'])
    # Reindex x to x_names
    X = X.reindex(task['x_names'], axis=1)
    # Load targets from excel file
    Y = pd.read_excel(
        task['PATH_TO_DATA'],
        sheet_name=task['SHEET_NAME'],
        header=0,
        usecols=task['Y_NAMES'],
        dtype=np.float64,
        skiprows=task['SKIP_ROWS'])

    # Prepare data ------------------------------------------------------------
    # Iterate over prediction targets (Y_NAMES)
    for i_y, y_name in enumerate(Y_NAMES):
        # Add prediction target index to task
        task['i_y'] = i_y
        # Add prediction target name to task
        task['y_name'] = [y_name]

        # Deal with NaNs in the target ----------------------------------------
        # Get current target and remove NaNs
        y = Y[y_name].to_frame().dropna()
        # Use y index for groups and reset index
        g = G.reindex(index=y.index).reset_index(drop=True)
        # Use y index for predictors and reset index
        x = X.reindex(index=y.index).reset_index(drop=True)
        # Reset index of target
        y = y.reset_index(drop=True)

        # Limit number of samples ---------------------------------------------
        # Subsample predictors
        x = x.sample(
            n=min(x.shape[0], task['MAX_SAMPLES']),
            random_state=None,
            ignore_index=False)
        # Slice group to fit subsampled predictors
        g = g.loc[x.index, :].reset_index(drop=True)
        # Slice targets to fit subsampled predictors
        y = y.loc[x.index, :].reset_index(drop=True)
        # Reset index of predictors
        x = x.reset_index(drop=True)

        # Store data ----------------------------------------------------------
        # Save groups
        g.to_excel(
            path_to_results+'/'+ANALYSIS_NAME+'_'+task['y_name'][0] +
            '_data_g.xlsx')
        # Save predictors
        x.to_excel(
            path_to_results+'/'+ANALYSIS_NAME+'_'+task['y_name'][0] +
            '_data_x.xlsx')
        # Save targets
        y.to_excel(
            path_to_results+'/'+ANALYSIS_NAME+'_'+task['y_name'][0] +
            '_data_y.xlsx')

        # Exploratory data analysis (EDA) -------------------------------------
        # Run EDA
        eda(task, g, x, y)

    # Return ------------------------------------------------------------------
    return


if __name__ == '__main__':
    main()
