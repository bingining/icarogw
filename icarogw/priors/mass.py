import numpy as _np
import copy as _copy
import sys as _sys
from . import custom_math_priors as _cmp
from scipy.interpolate import interp1d as _interp1d

from numpy import log, sqrt, exp, pi
import numpy as np
import os
from scipy.interpolate import interp2d

# # start of PBH mass function for pbh==========================================
# from julia.api import Julia
# jl = Julia(compiled_modules=False)
# jl.eval('include("/home/czc/projects/working/icarogw/examples/pbh_merger_rate.jl")')

# log_R_pbh_log = jl.eval('log_R_pbh_log')
# log_R_pbh_log_norm = jl.eval('log_R_pbh_log_norm')

# log_R_pbh_log_nocut = jl.eval('log_R_pbh_log_nocut')
# log_R_pbh_log_nocut_norm = jl.eval('log_R_pbh_log_nocut_norm')

# log_R_pbh_power = jl.eval('log_R_pbh_power')
# log_R_pbh_power_norm = jl.eval('log_R_pbh_power_norm')

# log_R_pbh_power_nocut = jl.eval('log_R_pbh_power_nocut')
# log_R_pbh_power_nocut_norm = jl.eval('log_R_pbh_power_nocut_norm')

# log_R_pbh_cc = jl.eval('log_R_pbh_cc')
# log_R_pbh_cc_norm = jl.eval('log_R_pbh_cc_norm')

# log_R_pbh_cc_nocut = jl.eval('log_R_pbh_cc_nocut')
# log_R_pbh_cc_nocut_norm = jl.eval('log_R_pbh_cc_nocut_norm')
# # end of PBH mass function for pbh==========================================


class mass_prior(object):
    """
    Wrapper for for managing the priors on source frame masses.
    The prior is factorized as :math:`p(m_1,m_2) \\propto p(m_1)p(m_2|m_1)`

    Parameters
    ----------
    name: str
        Name of the model that you want. Available 'BBH-powerlaw', 'BBH-powerlaw-gaussian'
        'BBH-broken-powerlaw', 'BBH-powerlaw-double-gaussian'.
    hyper_params_dict: dict
        Dictionary of hyperparameters for the prior model you want to use. See code lines for more details
    bilby_priors: boolean
        If you want to use bilby priors or not. It is faster to use the analytical functions.
    """

    def __init__(self, name, hyper_params_dict):

        self.name = name
        self.hyper_params_dict = _copy.deepcopy(hyper_params_dict)
        dist = {}

        if self.name == 'BBH-powerlaw':
            alpha = hyper_params_dict['alpha']
            beta = hyper_params_dict['beta']
            mmin = hyper_params_dict['mmin']
            mmax = hyper_params_dict['mmax']

            # Define the prior on the masses with a truncated powerlaw as in Eq.33,34,35 on the tex document
            dist = {'mass_1': _cmp.PowerLaw_math(alpha=-alpha, min_pl=mmin, max_pl=mmax),
                    'mass_2': _cmp.PowerLaw_math(alpha=beta, min_pl=mmin, max_pl=mmax)}

            self.mmin = mmin
            self.mmax = mmax

        elif self.name == 'BBH-powerlaw-gaussian':
            alpha = hyper_params_dict['alpha']
            beta = hyper_params_dict['beta']
            mmin = hyper_params_dict['mmin']
            mmax = hyper_params_dict['mmax']

            mu_g = hyper_params_dict['mu_g']
            sigma_g = hyper_params_dict['sigma_g']
            lambda_peak = hyper_params_dict['lambda_peak']

            delta_m = hyper_params_dict['delta_m']

            # Define the prior on the masses with a truncated powerlaw + gaussian
            # as in Eq.36-37-38 on the tex document
            m1pr = _cmp.PowerLawGaussian_math(alpha=-alpha, min_pl=mmin, max_pl=mmax, lambda_g=lambda_peak,
                                              mean_g=mu_g, sigma_g=sigma_g, min_g=mmin, max_g=mu_g+5*sigma_g)
            m2pr = _cmp.PowerLaw_math(
                alpha=beta, min_pl=mmin, max_pl=m1pr.maximum)

            # Smooth the lower end of these distributions
            dist = {'mass_1': _cmp.SmoothedProb(origin_prob=m1pr, bottom=mmin, bottom_smooth=delta_m),
                    'mass_2': _cmp.SmoothedProb(origin_prob=m2pr, bottom=mmin, bottom_smooth=delta_m)}

            # TODO Assume that the gaussian peak does not overlap too much with the mmin
            self.mmin = mmin
            self.mmax = dist['mass_1'].maximum

        elif self.name == 'BBH-powerlaw-double-gaussian':

            alpha = hyper_params_dict['alpha']
            beta = hyper_params_dict['beta']
            mmin = hyper_params_dict['mmin']
            mmax = hyper_params_dict['mmax']

            mu_g_low = hyper_params_dict['mu_g_low']
            sigma_g_low = hyper_params_dict['sigma_g_low']
            mu_g_high = hyper_params_dict['mu_g_high']
            sigma_g_high = hyper_params_dict['sigma_g_high']

            lambda_g = hyper_params_dict['lambda_g']
            lambda_g_low = hyper_params_dict['lambda_g_low']

            delta_m = hyper_params_dict['delta_m']

            # Define the prior on the masses with a truncated powerlaw + gaussian
            # as in Eq.45-46-448 on the tex document
            m1pr = _cmp.PowerLawDoubleGaussian_math(alpha=-alpha, min_pl=mmin, max_pl=mmax, lambda_g=lambda_g, lambda_g_low=lambda_g_low, mean_g_low=mu_g_low,
                                                    sigma_g_low=sigma_g_low, mean_g_high=mu_g_high, sigma_g_high=sigma_g_high, min_g=mmin, max_g=mu_g_high+5*_np.max([sigma_g_low, sigma_g_high]))
            m2pr = _cmp.PowerLaw_math(
                alpha=beta, min_pl=mmin, max_pl=m1pr.maximum)

            # Smooth the lower end of these distributions
            dist = {'mass_1': _cmp.SmoothedProb(origin_prob=m1pr, bottom=mmin, bottom_smooth=delta_m),
                    'mass_2': _cmp.SmoothedProb(origin_prob=m2pr, bottom=mmin, bottom_smooth=delta_m)}

            # TODO Assume that the gaussian peak does not overlap too much with the mmin
            self.mmin = mmin
            self.mmax = dist['mass_1'].maximum

        elif self.name == 'BBH-broken-powerlaw':
            alpha_1 = hyper_params_dict['alpha_1']
            alpha_2 = hyper_params_dict['alpha_2']
            beta = hyper_params_dict['beta']
            mmin = hyper_params_dict['mmin']
            mmax = hyper_params_dict['mmax']
            b = hyper_params_dict['b']

            delta_m = hyper_params_dict['delta_m']

            # Define the prior on the masses with a truncated powerlaw + gaussian
            # as in Eq.39-42-43 on the tex document
            m1pr = _cmp.BrokenPowerLaw_math(
                alpha_1=-alpha_1, alpha_2=-alpha_2, min_pl=mmin, max_pl=mmax, b=b)
            m2pr = _cmp.PowerLaw_math(alpha=beta, min_pl=mmin, max_pl=mmax)

            # Smooth the lower end of these distributions
            dist = {'mass_1': _cmp.SmoothedProb(origin_prob=m1pr, bottom=mmin, bottom_smooth=delta_m),
                    'mass_2': _cmp.SmoothedProb(origin_prob=m2pr, bottom=mmin, bottom_smooth=delta_m)}

            self.mmin = mmin
            self.mmax = mmax

        elif self.name == 'PBH-lognormal':
            self.mc = hyper_params_dict['mc']
            self.??c = hyper_params_dict['??c']
            self.m_min = hyper_params_dict['m_min']
            self.m_max = hyper_params_dict['m_max']

        elif self.name == 'PBH-lognormal-nocut':
            self.mc = hyper_params_dict['mc']
            self.??c = hyper_params_dict['??c']

        elif self.name == 'PBH-powerlaw':
            self.?? = hyper_params_dict['??']
            self.m_min = hyper_params_dict['m_min']
            self.m_max = hyper_params_dict['m_max']

        elif self.name == 'PBH-powerlaw-nocut':
            self.?? = hyper_params_dict['??']
            self.m_min = hyper_params_dict['m_min']

        elif self.name == 'PBH-cc':
            self.?? = hyper_params_dict['??']
            self.Mf = hyper_params_dict['Mf']
            self.m_min = hyper_params_dict['m_min']
            self.m_max = hyper_params_dict['m_max']

        elif self.name == 'PBH-cc-nocut':
            self.?? = hyper_params_dict['??']
            self.Mf = hyper_params_dict['Mf']

        else:
            print('Name not known, aborting')
            _sys.exit()

        self.dist = dist

    def joint_prob(self, ms1, ms2):
        """
        This method returns the joint probability :math:`p(m_1,m_2)`

        Parameters
        ----------
        ms1: np.array(matrix)
            mass one in solar masses
        ms2: dict
            mass two in solar masses
        """

        # Returns the joint probability Factorized as in Eq. 33 on the paper

        return _np.exp(self.log_joint_prob(ms1, ms2))

    def log_joint_prob(self, ms1, ms2):
        """
        This method returns the log of the joint probability :math:`p(m_1,m_2)`

        Parameters
        ----------
        ms1: np.array(matrix)
            mass one in solar masses
        ms2: dict
            mass two in solar masses
        """

        if self.name == 'PBH-lognormal':
            to_ret = log_R_pbh_log(ms1, ms2, self.mc, self.??c, self.m_min, self.m_max) - \
                log_R_pbh_log_norm(self.mc, self.??c, self.m_min, self.m_max)
        elif self.name == 'PBH-lognormal-nocut':
            to_ret = log_R_pbh_log_nocut(
                ms1, ms2, self.mc, self.??c) - log_R_pbh_log_nocut_norm(self.mc, self.??c)

        elif self.name == 'PBH-powerlaw':
            to_ret = log_R_pbh_power(ms1, ms2, self.??, self.m_min, self.m_max) - \
                log_R_pbh_power_norm(self.??, self.m_min, self.m_max)
        elif self.name == 'PBH-powerlaw-nocut':
            to_ret = log_R_pbh_power_nocut(
                ms1, ms2, self.??, self.m_min) - log_R_pbh_power_nocut_norm(self.??, self.m_min)

        elif self.name == 'PBH-cc':
            to_ret = log_R_pbh_cc(ms1, ms2, self.??, self.Mf, self.m_min, self.m_max) - \
                log_R_pbh_cc_norm(self.??, self.Mf, self.m_min, self.m_max)
        elif self.name == 'PBH-cc-nocut':
            to_ret = log_R_pbh_cc_nocut(
                ms1, ms2, self.??, self.Mf) - log_R_pbh_cc_nocut_norm(self.??, self.Mf)
        else:
            # Returns the joint probability Factorized as in Eq. 33 on the paper
            to_ret = self.dist['mass_1'].log_prob(
                ms1) + self.dist['mass_2'].log_conditioned_prob(ms2, self.mmin*_np.ones_like(ms1), ms1)

        to_ret[_np.isnan(to_ret)] = -_np.inf

        return to_ret

    def sample(self, Nsample):
        """
        This method samples from the joint probability :math:`p(m_1,m_2)`

        Parameters
        ----------
        Nsample: int
            Number of samples you want
        """

        vals_m1 = _np.random.rand(Nsample)
        vals_m2 = _np.random.rand(Nsample)

        m1_trials = _np.logspace(_np.log10(self.dist['mass_1'].minimum), _np.log10(
            self.dist['mass_1'].maximum), 50000)
        m2_trials = _np.logspace(_np.log10(self.dist['mass_2'].minimum), _np.log10(
            self.dist['mass_2'].maximum), 50000)

        cdf_m1_trials = self.dist['mass_1'].cdf(m1_trials)
        cdf_m2_trials = self.dist['mass_2'].cdf(m2_trials)

        log_m1_trials = _np.log10(m1_trials)
        log_m2_trials = _np.log10(m2_trials)

        _, indxm1 = _np.unique(cdf_m1_trials, return_index=True)
        _, indxm2 = _np.unique(cdf_m2_trials, return_index=True)

        interpo_icdf_m1 = _interp1d(cdf_m1_trials[indxm1], log_m1_trials[indxm1], bounds_error=False, fill_value=(
            log_m1_trials[0], log_m1_trials[-1]))
        interpo_icdf_m2 = _interp1d(cdf_m2_trials[indxm2], log_m2_trials[indxm2], bounds_error=False, fill_value=(
            log_m2_trials[0], log_m2_trials[-1]))

        mass_1_samples = 10**interpo_icdf_m1(vals_m1)
        mass_2_samples = 10**interpo_icdf_m2(vals_m2 *
                                             self.dist['mass_2'].cdf(mass_1_samples))

        to_ret = {'mass_1': mass_1_samples, 'mass_2': mass_2_samples}

        return to_ret['mass_1'], to_ret['mass_2']
