from .util import parse_checksum
from . import Backend, SeamlessTransformationError
from .shell_backend import launch

import time
from functools import partial
import subprocess
import sys, os
import asyncio

class GenericBackend(Backend):

    def __init__(self, *args, executor, **kwargs):
        self.executor = executor
        self.coros = {}
        super().__init__(*args, **kwargs)

    CONDA_ENV_RUN_TRANSFORMATION_COMMAND = "seamless-conda-env-run-transformation"

    def prepare_run_transformation_env(self, env):
        env.pop("SEAMLESS_DATABASE_IP", None)

    def get_job_status(self, checksum, identifier):
        return 2, None, None

    def _run(self, checksum, transformation, prepared_transformation):    
        errmsg = """
Generic transformer error
==========================

*************************************************
* Command
*************************************************
{}
*************************************************

*************************************************
* Standard output
*************************************************
{}
*************************************************

*************************************************
* Standard error
*************************************************
{}
*************************************************
"""        
        checksum = parse_checksum(checksum)
        cmd = [self.CONDA_ENV_RUN_TRANSFORMATION_COMMAND]
        d = prepared_transformation["temp_conda_env_directory"]
        cmd.append(d)
        cmd.append(checksum)
        filezones = prepared_transformation["filezones"]
        if filezones is not None:
            for filezone in filezones:
                cmd.append("--filezone")
                cmd.append(filezone)
        print("Running generic job for {}".format(checksum), file=sys.stderr)
        try:
            cmd2 = " ".join(cmd)
            env = os.environ.copy()            
            self.prepare_run_transformation_env(env)
            print("run transformation command:", cmd2)
            process = subprocess.run(
                cmd2, shell=True, check=True, capture_output=True, env=env
            )
        except subprocess.CalledProcessError as exc:
            stdout = exc.stdout
            try:
                stdout = stdout.decode()
            except:
                pass
            stderr = exc.stderr
            try:
                stderr = stderr.decode()
            except:
                pass
            raise SeamlessTransformationError(errmsg.format(cmd2, stdout, stderr)) from None

        result_checksum = self.database_client.get_transformation_result(checksum)
        if result_checksum is not None:
            return Checksum(result_checksum)

        cmd3 = cmd2 + "\n" + "Output is empty"
        stdout = process.stdout
        try:
            stdout = stdout.decode()
        except:
            pass
        stderr = process.stderr
        try:
            stderr = stderr.decode()
        except:
            pass

        raise SeamlessTransformationError(errmsg.format(cmd3, stdout, stderr)) from None

    def launch_transformation(self, checksum, transformation, prepared_transformation):
        checksum = parse_checksum(checksum)
        conda_env = prepared_transformation["conda_env"]
        self.transformation_to_conda_env[checksum] = conda_env
        self.conda_env_to_transformations[conda_env].append(checksum)
        self.conda_env_last_used[conda_env] = time.time()
        
        return launch(
            checksum, transformation, prepared_transformation, 
            self._run, self.coros, self.executor
        )


    async def run_transformation(self, checksum, transformation):
        await super().run_transformation(checksum, transformation)
        future = self.transformations[checksum] 
        future.add_done_callback(partial(self.transformation_finished2, checksum))


    def cancel_job(self, checksum, identifier):
        if checksum in self.coros:
            coro = self.coros.pop(checksum)
            task = asyncio.ensure_future(coro)
            task.cancel()

class GenericSingularityBackend(GenericBackend):
    SINGULARITY_IMAGE_FILE = None # to be defined by jobless
    
    def prepare_run_transformation_env(self, env):
        env["SEAMLESS_MINIMAL_SINGULARITY_IMAGE"] = self.SINGULARITY_IMAGE_FILE


from . import Checksum