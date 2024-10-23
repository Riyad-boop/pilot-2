import yaml
from subprocess import Popen, PIPE
import subprocess

class utils():
     
    def __init__(self) -> None:
        pass

    def load_yaml(self, path:str) -> dict:
        """
        Load a yaml file from the given path to a dictionary

        Args:
            path (str): path to the yaml file

        Returns:
            dict: dictionary containing the yaml file content

        """
        with open(path , 'r') as file:
            return yaml.safe_load(file)
        
    def run_shell_command(self, path_to_script:str) -> None:
        """
        Run a shell script command using subprocess.run

        Args:
            (path_to_script(str): The path to the shell script.
        """
        # run the shell script
        command = f"bash {path_to_script}"

        proc = Popen(command, shell=True, stdout=PIPE, stderr=PIPE)
        stdout, stderr = proc.communicate()
        print("Shell script executing ...")

        if proc.returncode != 0:
            #check if the output has syntax error
            if b"syntax error" in stderr:
                print("Syntax error in the shell script. \n Attempting to convert the shell script to Unix format.")
                # convert the shell script to unix format
                subprocess.run(f"dos2unix {path_to_script}", shell=True, text=True)
                # run the command again
                self.run_shell_command(path_to_script)
            else:
                raise subprocess.CalledProcessError(proc.returncode, command, output=stdout, stderr=stderr)
        else:
            print(stdout.decode('utf-8'))