import pymc3 as pm
import theano.tensor as tt
from theano import shared
import numpy as np
import scipy as sp
# theano.config.gcc.cxxflags = "-fbracket-depth=16000" # default is 256

class Ornstein_Uhlenbeck(pm.Continuous):
    """
    Ornstein-Uhlenbeck Process
    Parameters
    ----------
    B : tensor
        B > 0, B = exp(-(D/A)*delta_t)
    A : tensor
        A > 0, amplitude of fluctuation <x**2>=A
    delta_t: scalar
        delta_t > 0, time step
    """

    def __init__(self, A=None, B=None,
                 *args, **kwargs):
        super(Ornstein_Uhlenbeck, self).__init__(*args, **kwargs)
        self.A = A
        self.B = B
        self.mean = 0.

    def logp(self, x):
        A = self.A
        B = self.B

        x_im1 = x[:-1]
        x_i = x[1:]

        ou_like = pm.Normal.dist(mu=x_im1*B, tau=1.0/A/(1-B**2)).logp(x_i)
        return pm.Normal.dist(mu=0.0,tau=1.0/A).logp(x[0]) + tt.sum(ou_like)

class BayesianModel(object):
    samples = 10000
    target_accept = 0.8

    def __init__(self, cache_model=True):
        self.cached_model = None
        self.cached_start = None
        self.cached_sampler = None
        self.shared_vars = {}

    def cache_model(self, **inputs):
        self.shared_vars = self._create_shared_vars(**inputs)
        self.cached_model = self.create_model(**self.shared_vars)

    def create_model(self, **inputs):
        raise NotImplementedError('This method has to be overwritten.')

    def _create_shared_vars(self, **inputs):
        shared_vars = {}
        for name, data in inputs.items():
            shared_vars[name] = shared(np.asarray(data), name=name)
        return shared_vars

    def run(self, reinit=True, **inputs):
        if self.cached_model is None:
            self.cache_model(**inputs)

        for name, data in inputs.items():
            self.shared_vars[name].set_value(data)

        trace = self._inference(reinit=reinit)
        return trace

    def _inference(self, reinit=True):
        with self.cached_model:
            trace = pm.sample(samples=self.samples,target_accept=self.target_accept)

        return trace


class OU_DA(BayesianModel):
    """Bayesian model for a Ornstein-Uhlenback process.
    The model has inputs x, and prior parameters for
    uniform distributions for D and A
    """

    def create_model(self, x=None, d_bound=None, a_bound=None, delta_t=None, N=None):
        with pm.Model() as model:
            D = pm.Uniform('D', lower=0, upper=d_bound)
            A = pm.Uniform('A', lower=0, upper=a_bound)

            B = pm.Deterministic('B', pm.math.exp(-delta_t * D / A))

            path = Ornstein_Uhlenbeck('path',A=A, B=B, observed=x)
        return model
    

class OU_BA(BayesianModel):
    """Bayesian model for a Ornstein-Uhlenback process.
    The model has inputs x, and prior parameters for
    uniform distributions for B and A
    """

    def create_model(self, x=None, b_bound=None, a_bound=None, delta_t=None, N=None):
        with pm.Model() as model:
            B = pm.Uniform('B', lower=0, upper=b_bound)
            A = pm.Uniform('A', lower=0, upper=a_bound)

            path = Ornstein_Uhlenbeck('path',B=B, A=A, observed=x)
        return model

class LangevinPlusNoiseIG(BayesianModel):
    """Bayesian model for a Ornstein-Uhlenback process + noise.
    The model has inputs x, and prior parameters for
    gamma distributions for D and A
    """

    def create_model(self, x=None, aD=None, bD=None, aA=None, bA=None, aN=None, bN=None, delta_t=None, N=None):
        with pm.Model() as model:
            D = pm.InverseGamma('D', alpha=aD, beta=bD)
            A = pm.Gamma('A', alpha=aA, beta=bA)
            sN = pm.InverseGamma('sN', alpha=aN, beta=bN)

            B = pm.Deterministic('B', pm.math.exp(-delta_t * D / A))

            path = Ornstein_Uhlenbeck('path',A=A, B=B, shape=(N,))

            X_obs = pm.Normal('X_obs', mu=path, sd=sN, observed=x)

        return model

class LangevinIG2(BayesianModel):
    """Bayesian model for a Ornstein-Uhlenback process.
    The model has inputs x, and prior parameters for
    gamma distributions for D and A
    """

    def create_model(self, x1=None, x2=None, aD=None, bD=None, aA1=None, bA1=None, aA2=None, bA2=None, delta_t=None, N=None):
        with pm.Model() as model:
            D = pm.InverseGamma('D', alpha=aD, beta=bD)
            A1 = pm.Gamma('A1', alpha=aA1, beta=bA1)
            A2 = pm.Gamma('A2', alpha=aA2, beta=bA2)

            B1 = pm.Deterministic('B1', pm.math.exp(-delta_t * D / A1))
            B2 = pm.Deterministic('B2', pm.exp.math(-delta_t * D / A2))

            path1 = Ornstein_Uhlenbeck('path1',A=A1, B=B1, observed=x1)
            path2 = Ornstein_Uhlenbeck('path2', A=A2, B=B2, observed=x2)
        return model
