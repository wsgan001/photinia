#!/usr/bin/env python3

"""
@author: xi
@since: 2016-11-11
"""

import collections

import tensorflow as tf

from . import widgets
from .. import ops
from .. import settings


class Slot(object):

    def __init__(self,
                 inputs=None,
                 outputs=None,
                 updates=None,
                 givens=None,
                 callbacks=None):
        """A slot object is a callable which accepts multiple tensor inputs
        and gives out multiple outputs.

        Args:
            inputs (list[tf.Tensor]|tuple[tf.Tensor]|tf.Tensor):
                Input tensor(s).
            outputs (dict[str, tf.Tensor]|list[tf.Tensor]|tuple[tf.Tensor]|tf.Tensor):
                Output tensor(s).
            updates (list[tf.Operation]|tuple[tf.Operation]|tf.Operation):
                Operation(s) when invoked. These are usually generated by optimizers.
            givens (dict[tf.Tensor, Any]):
                Preset values for some placeholder, e.g., the keep_prob value for dropout.
            callbacks (list[(Any) -> None]|tuple[(Any) -> None]|(Any) -> None): Callback(s)

        """
        self._session = settings.get_session()
        #
        # Inputs.
        if inputs is None:
            inputs = ()
        if not isinstance(inputs, (tuple, list)):
            inputs = (inputs,)
        self._inputs = inputs
        #
        # Outputs.
        if outputs is None:
            outputs = ()
        if not isinstance(outputs, (tuple, list)) \
                and not isinstance(outputs, (dict, collections.OrderedDict)):
            outputs = (outputs,)
        self._outputs = outputs
        #
        # Updates.
        if updates is None:
            updates = ()
        if not isinstance(updates, (tuple, list)):
            updates = (updates,)
        self._updates = updates
        #
        # Givens.
        if givens is None:
            givens = {}
        if not isinstance(givens, dict):
            raise ValueError('Givens must be dict.')
        self._givens = givens
        #
        # Callbacks.
        if callbacks is None:
            callbacks = ()
        if not isinstance(callbacks, (tuple, list)):
            callbacks = (callbacks,)
        self._callbacks = callbacks
        #
        self._feed_dict = givens.copy()
        self._fetches = (outputs, updates)
        if len(outputs) == 0 and len(updates) == 0:
            raise ValueError('At least one output or update should be set.')

    @property
    def outputs(self):
        return self._outputs

    @property
    def inputs(self):
        return self._inputs

    @property
    def updates(self):
        return self._updates

    @property
    def givens(self):
        return self._givens

    def __call__(self, *args):
        #
        # Check input length.
        if len(args) != len(self._inputs):
            print(len(args), len(self._inputs))
            raise ValueError('The count of parameters is not match the inputs.')
        #
        # Make "feed_dict".
        for index, placeholder in enumerate(self._inputs):
            self._feed_dict[placeholder] = args[index]
        #
        # Run the graph on the session.
        ret = self._session.run(fetches=self._fetches, feed_dict=self._feed_dict)[0]
        for callback in self._callbacks:
            callback(ret)
        return ret


class Model(widgets.Trainable):
    """Model
    """

    def __init__(self, name, build=True):
        """Construct a trainer.

        A trainer is a special widget which should not be regarded as
        a part of your model structure. Normally, a trainer contains
        procedure to build the model widgets and define slots to learn
        the model parameters.

        Args:
            name (str): Widget/Model name.
            build (bool): If the widget will be built during the construction.

        """
        self._slots = {}
        super(Model, self).__init__(name, build)

    def _build(self):
        """Build the model.
        Abstract method.
        All subclass must implement this method.

        There are at least two tasks to be done in this method:
        1) Construct the model's graph structure with TF.
        2) Define and add slots for training, evaluation and prediction.

        """
        raise NotImplementedError()

    def _add_slot(self,
                  name,
                  inputs=None,
                  outputs=None,
                  givens=None,
                  updates=None,
                  callbacks=None):
        """A slot object is a callable which accepts multiple tensor inputs
        and gives out multiple outputs.

        Args:
            inputs (list[tf.Tensor]|tuple[tf.Tensor]|tf.Tensor):
                Input tensor(s).
            outputs (dict[str, tf.Tensor]|list[tf.Tensor]|tuple[tf.Tensor]|tf.Tensor):
                Output tensor(s).
            updates (list[tf.Operation]|tuple[tf.Operation]|tf.Operation):
                Operation(s) when invoked. These are usually generated by optimizers.
            givens (dict[tf.Tensor, Any]):
                Preset values for some placeholder, e.g., the keep_prob value for dropout.
            callbacks (list[(Any) -> None]|tuple[(Any) -> None]|(Any) -> None): Callback(s)

        """
        if name in self._slots:
            raise ValueError(
                'Slot % exists.' % name
            )
        if getattr(self, name) is not None:
            raise ValueError(
                'Invalid slot name %s. Cannot be the same as any of the method name of the trainer.' % name
            )
        slot = Slot(
            inputs=inputs,
            outputs=outputs,
            updates=updates,
            givens=givens,
            callbacks=callbacks
        )
        self._slots[name] = slot
        setattr(self, name, slot)

    def get_slot(self, name):
        """Get the slot object.

        Args:
            name (str): Slot name.

        Returns:
            Slot: The slot object.

        """
        if name not in self._slots:
            raise KeyError(
                'Trainer %s does not have a slot named %s.' % (self._full_name, name)
            )
        return self._slots[name]

# class MPIDispatcher(Fitter):
#     """MPI Dispatcher
#
#     This class is used for the distributional training of the model. (Based on MPI).
#     So, the servers should have one of the MPI implementation (e.g., openmpi, mpich) installed.
#     If this fitter is instanced and added to a trainer, the program should be run using the MPI command:
#
#         mpiexec -n {num_processes} python3 {python_file.py}
#     """
#
#     def __init__(self,
#                  sync_interval=2):
#         super(MPIDispatcher, self).__init__(1, 1)
#         from mpi4py import MPI
#         self._sync_interval = sync_interval
#         #
#         self._comm = MPI.COMM_WORLD
#         self._rank = self._comm.Get_rank()
#         self._size = self._comm.Get_size()
#         #
#         # This is very important since we should let the processes to use DIFFERENT GPUs of the same server.
#         # While, if the processes run on different servers, this can cause problems.
#         # TODO: Thus we need to further modify the assign policy to choose the GPU automatically.
#         gpu_list = [int(item) for item in os.environ['CUDA_VISIBLE_DEVICES'].split(',')]
#         gpu = gpu_list[self._rank % len(gpu_list)]
#         os.environ['CUDA_VISIBLE_DEVICES'] = str(gpu)
#
#     def _fit(self, i, max_loop, context):
#         trainer = context[settings.CONTEXT_TRAINER]
#         if i == 1:
#             self._init_all(trainer)
#         elif i % self._sync_interval == 0:
#             self._update_all(trainer)
#
#     def _init_all(self, trainer):
#         if self._rank == 0:
#             self._comm.bcast(trainer.parameters, root=0)
#         else:
#             trainer.parameters = self._comm.bcast(None, root=0)
#
#     def _update_all(self, trainer):
#         if self._rank == 0:
#             #
#             # Gather parameters from all processes (include the master itself).
#             # Compute the mean value for each parameter.
#             # Then, broadcast them.
#             param_list = self._comm.gather(trainer.parameters, root=0)
#             new_params = collections.defaultdict(list)
#             for params in param_list:
#                 for name, value in params.items():
#                     new_params[name].append(value)
#             new_params = {key: np.mean(value_list, axis=0) for key, value_list in new_params.items()}
#             new_params = trainer.parameters = self._comm.bcast(new_params, root=0)
#         else:
#             self._comm.gather(trainer.parameters, root=0)
#             new_params = self._comm.bcast(None, root=0)
#         #
#         # Update the parameters to the same version for all processes.
#         trainer.parameters = new_params
