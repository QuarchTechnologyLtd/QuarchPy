import unittest
import subprocess
from unittest.mock import Mock
from performanceClass import FioPerformance

class TestFioClass(unittest.TestCase):

    ####################################################################################################################
    # Necessary class variables for tests
    ####################################################################################################################

    testFile = "fio_tests_file.fio"
    test_dummy_output = "live_fio_output.txt"

    ####################################################################################################################
    # Testing no parameters
    ####################################################################################################################

    @unittest.mock.patch('subprocess.call')
    def test_no_parameters(self, os_system):
        # Testing only passing end callback

        x = FioPerformance()
        self.assertTrue(x.start_workload())


    ####################################################################################################################
    # Testing Callbacks
    ####################################################################################################################

    def test_callbacks_assigned(self):
        # Test to check program assigns callbacks

        newClass = Mock()

        callbacks = {"workload_start_callback": newClass.a(),
                      "workload_end_callback": newClass.b(),
                      "stream_data_callback": newClass.c()}

        x = FioPerformance()

        self.assertFalse(x.start_workload(output_data={"stream_workload_callbacks": callbacks}))

    def test_none_callback_function(self):
        # Test to check the program doesn't fail with bad parameters assigned for callbacks

        callbacks = {"workload_start_callback": "test",
                     "workload_end_callback": "test",
                     "stream_data_callback": "test"}

        x = FioPerformance()

        command = " ".join(x.command)

        self.assertEqual(command,"fio")

        self.assertFalse(x.start_workload(output_data={"stream_workload_callbacks": callbacks}))

    ####################################################################################################################
    # Testing File parsing
    ####################################################################################################################

    def test_workload_file_param_parsing(self):
        # Testing
        x = FioPerformance()

        f = open(self.testFile, "w")
        f.write("[global]\r"
                "write_iops_log=test\r"
                "write_lat_log=test\r"
                "[job1]")
        f.close()

        self.assertFalse(x.start_workload(workload_file_path=self.testFile))

        self.assertEqual(x.iops_log_output_file,"test_iops.1.log" )
        self.assertEqual(x.lat_log_output_file, "test_lat.1.log")
        self.assertEqual(x.clat_log_output_file, "test_clat.1.log")
        self.assertEqual(x.slat_log_output_file, "test_slat.1.log")
        # Check job1 is in one of the items of job name
        self.assertTrue("job1" in x.job_name)

    def test_workload_file_checking_multiple_jobs(self):
        # Testing
        x = FioPerformance()

        f = open(self.testFile, "w")
        f.write("[global]\r"
                "write_iops_log=test\r"
                "[job1]\r"
                "[job2]")
        f.close()

        self.assertFalse(x.start_workload(workload_file_path=self.testFile))

        # Check job1 is in one of the items of job name
        self.assertTrue("job1" in x.job_name)
        self.assertTrue("job2" in x.job_name)

    def test_workload_file_none_existant(self):
        # Testing
        x = FioPerformance()

        self.assertFalse(x.start_workload(workload_file_path="test_test.txt"))

        # Check job1 is in one of the items of job name
        self.assertFalse("test_test.txt" in x.command)

    ####################################################################################################################
    # Testing workload arguments
    ####################################################################################################################

    @unittest.mock.patch('subprocess.call')
    def test_workload_args_assignment(self, os_system):
        # Testing
        x = FioPerformance()

        workload_dict = { "read_percentage": 1,
                          "sequential": True,
                          "workload_file_size": "128kb",
                          "blocksize": "8k",
                          "runtime": 10,
                          "rampup_time": 10,
                          }

        self.assertTrue(x.start_workload(workload_args_dict=workload_dict))

        execution_string_contents = [ "--size=128kb", "--blocksize=8k", "--runtime=10", "--ramp_time=10",
                                      "--time_based", "--rw=rw", "--rwmixread=1" ]

        self.assertTrue(all(arg in x.command for arg in execution_string_contents))

    @unittest.mock.patch('subprocess.call')
    def test_workload_args_random_read(self, os_system):
        # Testing
        x = FioPerformance()

        workload_dict = {"read_percentage": 100,
                         "sequential": False
                         }

        self.assertFalse(x.start_workload(workload_args_dict=workload_dict))

        execution_string_contents = ["--rw=randread"]

        self.assertTrue(all(arg in x.command for arg in execution_string_contents))

    @unittest.mock.patch('subprocess.call')
    def test_workload_args_sequential_read(self, os_system):
        # Testing
        x = FioPerformance()

        workload_dict = {"read_percentage": 100,
                         "sequential": True
                         }

        self.assertFalse(x.start_workload(workload_args_dict=workload_dict))

        execution_string_contents = ["--rw=read"]

        self.assertTrue(all(arg in x.command for arg in execution_string_contents))

    @unittest.mock.patch('subprocess.call')
    def test_workload_args_random_write(self, os_system):
        # Testing
        x = FioPerformance()

        workload_dict = {"read_percentage": 0,
                         "sequential": False
                         }

        self.assertFalse(x.start_workload(workload_args_dict=workload_dict))

        execution_string_contents = ["--rw=randwrite"]

        self.assertTrue(all(arg in x.command for arg in execution_string_contents))

    @unittest.mock.patch('subprocess.call')
    def test_workload_args_sequential_write(self, os_system):
        # Testing
        x = FioPerformance()

        workload_dict = {"read_percentage": 0,
                         "sequential": True
                         }

        self.assertFalse(x.start_workload(workload_args_dict=workload_dict))

        execution_string_contents = ["--rw=write"]

        self.assertTrue(all(arg in x.command for arg in execution_string_contents))

    @unittest.mock.patch('subprocess.call')
    def test_workload_args_sequential_rw(self, os_system):
        # Testing
        x = FioPerformance()

        workload_dict = {"read_percentage": 1,
                         "sequential": True
                         }

        self.assertFalse(x.start_workload(workload_args_dict=workload_dict))

        execution_string_contents = ["--rw=rw"]

        self.assertTrue(all(arg in x.command for arg in execution_string_contents))

    @unittest.mock.patch('subprocess.call')
    def test_workload_args_random_rw(self, os_system):
        # Testing
        x = FioPerformance()

        workload_dict = {"read_percentage": 1,
                         "sequential": False
                         }

        self.assertFalse(x.start_workload(workload_args_dict=workload_dict))

        execution_string_contents = ["--rw=randrw"]

        self.assertTrue(all(arg in x.command for arg in execution_string_contents))

    ####################################################################################################################
    # Testing output arguments
    ####################################################################################################################

    @unittest.mock.patch('subprocess.call')
    def test_output_args_parse_high_res_data(self, os_system):
        # Testing
        x = FioPerformance()

        output_dict = {"high_res_data":
                           ["high_res_lat", "high_res_iops"]
                         }

        self.assertFalse(x.start_workload(output_data=output_dict))

        execution_string_contents = ["--write_iops_log="+x.iops_file_prefix, "--write_lat_log="+x.latency_file_prefix]

        self.assertTrue(all(arg in x.command for arg in execution_string_contents))

    @unittest.mock.patch('subprocess.call')
    def test_output_args_parse_stream_resolutions(self, os_system):
        # Testing
        x = FioPerformance()

        output_dict = {"stream_resolution": {"high_res_data_res": 1, "stream_data_res": 1}}

        self.assertFalse(x.start_workload(output_data=output_dict))

        execution_string_contents = ["--log_avg_msec=1",
                                     "--status-interval=1"]

        self.assertTrue(all(arg in x.command for arg in execution_string_contents))

    @unittest.mock.patch('subprocess.call')
    def test_output_args_parse_stream_resolutions_default_status_interval(self, os_system):
        # Testing
        x = FioPerformance()

        output_dict = {"stream_resolution": {"stream_data_res": 0}}

        self.assertFalse(x.start_workload(output_data=output_dict))

        execution_string_contents = ["--status-interval=1"]

        self.assertTrue(all(arg in x.command for arg in execution_string_contents))

    ####################################################################################################################
    # Testing executing FIO
    ####################################################################################################################

        # couldn't get the file to work as required
        # f = open(self.testFile, "w")
        # f.write("[global]\r"
        #         "size=64mb\r"
        #         "rw=read\r"
        #         "runtime=10\r"
        #         "directory=D\\:\\\r"
        #         "[job1]\r")
        # f.close()

    @unittest.mock.patch('subprocess.call')
    def test_execution_without_FIO_installed(self, sub_process):
        # Testing execution - No Output - simple args
        x = FioPerformance()

        # Missing FIO from system raises a file not found error
        sub_process.side_effect = FileNotFoundError

        workload_args = {"read_percentage": 100,
                         "sequential": True,
                         "runtime": 10,
                         "workload_file_size": "64k"}

        # Assert that the program raised the error and exited with it
        with self.assertRaises(Exception):
            x.start_workload(workload_args_dict=workload_args)

    @unittest.mock.patch('subprocess.call')
    def test_execution(self, os_system):
        # Testing execution - No Output - simple args
        x = FioPerformance()

        workload_args = {"read_percentage": 100,
                          "sequential": True,
                          "runtime": 10,
                          "workload_file_size": "64k"}

        x.start_workload(workload_args_dict=workload_args)
        # os.system was called once - Sufficient arguments passed
        self.assertTrue(os_system.called_once)

    @unittest.mock.patch('subprocess.call')
    def test_execution_returns_true(self, os_system):
        # Testing execution - No Output - simple args
        x = FioPerformance()

        workload_args = {"read_percentage": 100,
                          "sequential": True,
                          "runtime": 10,
                          "workload_file_size": "64k"}

        # function returned true
        self.assertTrue(x.start_workload(workload_args_dict=workload_args))


    def test_execution_async_returns_fio_process(self):
        # Testing that asynv returns a subprocess
        # TEST WILL MAKE A 64KB FILE IN CURRENT WORKING DIRECTORY

        # Testing execution - No Output - simple args
        x = FioPerformance()

        workload_args = {"read_percentage": 100,
                          "sequential": True,
                          "runtime": 10,
                          "workload_file_size": "64k"}

        ret_val = x.start_workload(workload_args_dict=workload_args, run_async=True)

        # checking is of type subprocess.Popen
        self.assertTrue(isinstance(ret_val, subprocess.Popen))

        ret_val.kill()
        ret_val.wait(3)

    @unittest.mock.patch('subprocess.Popen')
    def test_execution_async_process_called_once(self, sub_process):
        # Testing execution - No Output - simple args
        x = FioPerformance()

        workload_args = {"read_percentage": 100,
                         "sequential": True,
                         "runtime": 10,
                         "workload_file_size": "64k"}

        ret_val = x.start_workload(workload_args_dict=workload_args, run_async=True)

        self.assertTrue(sub_process.called_once)

        ret_val.kill()
        ret_val.wait(3)

    @unittest.mock.patch('subprocess.Popen')
    def test_execution_async_process_called_once(self, sub_process):
        # Testing execution - No Output - simple args
        x = FioPerformance()

        workload_args = {"read_percentage": 100,
                         "sequential": True,
                         "runtime": 10,
                         "workload_file_size": "64k"}

        ret_val = x.start_workload(workload_args_dict=workload_args, run_async=True)

        self.assertTrue(sub_process.called_once)

        ret_val.kill()
        ret_val.wait(3)

    @unittest.mock.patch('subprocess.Popen')
    def test_execution_non_sync_process_called_once(self, sub_process):
        # Testing execution - No Output - simple args
        x = FioPerformance()
        new_var = Mock()

        workload_args = {"read_percentage": 100,
                         "sequential": True,
                         "runtime": 10,
                         "workload_file_size": "64k"}

        callbacks = {"workload_start_callback": new_var.b()}
        x = FioPerformance()

        # Starting the function with a callback to go into the second tree
        ret_val = x.start_workload(workload_args_dict=workload_args,
                                   output_data={"stream_workload_callbacks": callbacks} )

        self.assertTrue(sub_process.called_once)

    ####################################################################################################################
    # Testing outputs
    ####################################################################################################################

    @unittest.mock.patch('subprocess.call')
    def test_results_simple_outputs(self, os_system):
        # Testing execution - No Output - simple args
        x = FioPerformance()

        workload_args = {"read_percentage": 100,
                         "sequential": True,
                         "runtime": 10,
                         "workload_file_size": "64k"}

        output = {"summary_data": ["read_iops", "write_iops"]}

        ret_val = x.start_workload(workload_args_dict=workload_args, output_data=output)
        # os.system was called once - Sufficient arguments passed
        self.assertTrue(os_system.called)
        # check the output included a dictionary format
        self.assertTrue(isinstance(ret_val, dict))
        # check the output contains 2 keys - 'read_iops' and 'write_iops'
        self.assertTrue(all(key in output["summary_data"] for key in ret_val.keys()))

    @unittest.mock.patch('subprocess.call')
    def test_results_custom_outputs(self, os_system):
        # Testing execution - No Output - simple args
        x = FioPerformance()

        workload_args = {"read_percentage": 100,
                         "sequential": True,
                         "runtime": 10,
                         "workload_file_size": "64k"}

        output = {"summary_data": ["find:jobs:jobname"]}

        ret_val = x.start_workload(workload_args_dict=workload_args, output_data=output)
        # os.system was called once - Sufficient arguments passed
        self.assertTrue(os_system.called)
        # check the output included a dictionary format
        self.assertTrue(isinstance(ret_val, dict))
        # check the output contains correct key output
        self.assertTrue("jobs:jobname" in ret_val.keys())

    @unittest.mock.patch('subprocess.call')
    def test_results_bad_custom_output(self, os_system):
        # Testing execution - No Output - simple args
        x = FioPerformance()

        workload_args = {"read_percentage": 100,
                         "sequential": True,
                         "runtime": 10,
                         "workload_file_size": "64k"}

        output = {"summary_data": ["find:jobs:jobname1"]}

        ret_val = x.start_workload(workload_args_dict=workload_args, output_data=output)
        # os.system was called once - Sufficient arguments passed
        self.assertTrue(os_system.called)
        # check the output included a dictionary format
        self.assertTrue(isinstance(ret_val, dict))
        # check the output contains correct key output
        self.assertEqual(ret_val["jobs:jobname1"], "Not Found")

    @unittest.mock.patch('subprocess.call')
    def test_results_bad_custom_search(self, os_system):
        # Testing execution - No Output - simple args
        x = FioPerformance()

        workload_args = {"read_percentage": 100,
                         "sequential": True,
                         "runtime": 10,
                         "workload_file_size": "64k"}

        output = {"summary_data": ["afind:jobs:jobname"]}

        ret_val = x.start_workload(workload_args_dict=workload_args, output_data=output)
        # os.system was called once - Sufficient arguments passed
        self.assertTrue(os_system.called)
        # check the output included a dictionary format
        self.assertTrue(isinstance(ret_val, dict))
        # check the output contains correct key output
        self.assertEqual(ret_val["afind:jobs:jobname"], "Invalid Summary Data Value")

    def test_results_callbacks(self):
        # Testing execution - No Output - simple args
        x = FioPerformance()

        workload_args = {"read_percentage": 100,
                         "sequential": True,
                         "runtime": 1,
                         "workload_file_size": "4k"}

        # Create a new mock
        mock_callback = Mock()
        # Assign some methods to the mocks
        callbacks = {"workload_start_callback": mock_callback.a(),
                     "workload_end_callback": mock_callback.b(),
                     "stream_data_callback": mock_callback.c()}

        x.start_workload(workload_args_dict=workload_args, output_file_path=self.test_dummy_output,
                         output_data={"stream_workload_callbacks": callbacks})

        mock_callback.a.assert_called_once()
        mock_callback.b.assert_called_once()
        mock_callback.c.assert_called()


    def test_results_high_res_arrays(self):
        # Testing execution - No Output - simple args
        x = FioPerformance()

        workload_args = {"read_percentage": 100,
                         "sequential": True,
                         "runtime": 10,
                         "workload_file_size": "64k"}

        output = {"high_res_data": ["high_res_lat"]}

        ret_val = x.start_workload(workload_args_dict=workload_args, output_data=output)
        # check the output included a dictionary format
        self.assertTrue(isinstance(ret_val, dict))
        key_list = ["time_lat_mS", "lat_log", "time_clat_mS", "clat_log", "time_slat_mS", "slat_log",
                     "time_iops_mS", "iops_log"]

        self.assertTrue(all(item in key_list for item in ret_val["high_res_data"]))




if __name__ == "__main__":
    unittest.main()
