"""conftest.py module for testing."""
# import pytest
# from scottbrian_algo1.diag_msg import DiagMsg
# # from threading import Thread  #, Event
# from datetime import datetime
# import time
#
#
# # def ptm(*args, **kwargs):
# #     """return time.
# #
# #     Returns:
# #         time as str
# #     """
# #     current_time = datetime.now()
# #     strtime = current_time.strftime("%H:%M:%S.%f")
# #     a, *b = args
# #     a = strtime + ' ' + str(a)
# #     print(a, *b, **kwargs)
# #     return
#
#
# class TAlgoApp(AlgoApp):
#     def __init__(self):
#         """TAlgoApp init."""
#
#         # ptm('SBT TAlgoApp:__init__ entered')
#         AlgoApp.__init__(self)
#         # self.run_thread = Thread(target=self.run)
#         # ptm('SBT TAlgoApp:__init__ exiting')
#
#     def run(self):
#         ptm( 'SBT TAlgoApp: run entered')
#         for i in range(5):
#             time.sleep(1)
#             if i == 3:
#                 ptm('SBT TAlgoApp: about to call nextValidId')
#                 self.nextValidId(1)
#
#
#
# @pytest.fixture(scope='session')
# def diag_msg() -> "AlgoApp":
#     """Instantiate and return an AlgoApp for testing.
#
#     Returns:
#         An instance of AlgoApp
#     """
#     a_algo_app = TAlgoApp()
#     return a_algo_app
