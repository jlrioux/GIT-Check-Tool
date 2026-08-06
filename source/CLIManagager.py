# CLIManagager.py
# ----------------
# This module provides a command-line interface (CLI) manager for a Git
# repository checking tool. It coordinates user input from the CLI with the
# underlying RepoManager, and communicates status updates back to the UI
# through callback functions.

# Standard library imports:
#   sys     - (reserved) provides access to system-specific parameters/functions
#   time    - used for sleep/polling delays while waiting for user input
#   threading - provides the Lock and Thread objects used to synchronize input
#   re      - provides regular expression support for input validation
import sys,time,threading,re
# Project import: RepoManager handles the actual Git repository operations
from RepoLibClass import RepoManager


class CLIManagerClass():
    # ------------------------------------------------------------------
    # Class-level (shared) attributes
    # ------------------------------------------------------------------
    __input_lock = threading.Lock()  # Shared lock used to synchronize CLI input
    printout = None                  # Callback used to print text to the UI
    clearout = None                  # Callback used to clear the UI output
    update_status = None             # Callback used to update the UI status

    def __init__(self,printout,clearout,update_status):
        # Initialize the CLI manager with the provided UI callbacks.
        # The RepoManager is created lazily in Start() (commented line below).
        self.repos = None#RepoManager(printout,update_status)
        CLIManagerClass.printout = printout
        CLIManagerClass.clearout = clearout
        CLIManagerClass.update_status = update_status

        # Storage for the most recent user response and a flag indicating
        # that the response is expected to be a directory path.
        self.__user_response = ''
        self.__user_response_dir = False

        # Create a background daemon thread that continuously processes
        # CLI input. The thread target is the inner 'run' function returned
        # by __process_input_thread().
        self.__process = threading.Thread(target=self.__process_input_thread(),daemon=True)

    def Start(self,allow_toast):
        # Create the RepoManager with the shared callbacks, passing whether
        # toast notifications are allowed, then start the background thread.
        self.repos = RepoManager(CLIManagerClass.printout,CLIManagerClass.update_status,allow_toast)
        self.__process.start()


    def user_response(self,text):
        # Called by the UI when the user submits a response.
        # If we are currently expecting a directory path, store the response
        # and release the input lock so input() returns.
        if self.__user_response_dir:
            self.__user_response = text
            CLIManagerClass.__input_lock.release()
        # Ignore responses that are not the 'resetUI' command and do not
        # match a comma-separated list of numbers.
        if text != 'resetUI' and not re.match(r'^\d+(?:,\s*\d+)*$',text):return
        # Store the validated response, echo it back to the UI, and release
        # the input lock so the waiting input() call can proceed.
        self.__user_response = text
        CLIManagerClass.printout('< ' + text + '\n')
        CLIManagerClass.__input_lock.release()
    def input(self,text):
        # Display a prompt to the user, then block (acquire the lock) until
        # a response is received via user_response(). Poll the lock every
        # 0.1 seconds while waiting, then return and reset the stored value.
        CLIManagerClass.printout('> ' + text)
        CLIManagerClass.__input_lock.acquire()
        while CLIManagerClass.__input_lock.locked():
            time.sleep(0.1)
        value = self.__user_response
        self.__user_response = ''
        return value
        
    def __process_input_thread(self):
        # Returns a 'run' closure that loops forever, processing input and
        # then sleeping briefly. Used as the body of the background thread.
        def run():
            while(True):
                self.__process_input()
                time.sleep(0.5)
        return run
    def __process_input(self):
        # Update the UI status to reflect the current repo status.
        CLIManagerClass.update_status(self.repos.current_status)
        # If no root directory has been set yet, prompt the user for one.
        if not self.repos.root_directory_set:
            self.__user_response_dir = True
            dir = self.input('Enter root directory for responsitories:\n')
            self.__user_response_dir = False
            self.repos.set_root_directory(dir)
            return
        # Display the main menu and read the user's chosen action.
        action = self.input("""\nMain Menu:
    0. Set root directory for repositories
    1. Check all repositories for changes
    2. Pull for certain repositories
    3. Pull for all repositories
What would you like to do? :\n""")
        CLIManagerClass.clearout()
        # Default to action '1' if an invalid selection was entered.
        if action not in ['0','1','2','3']:action = '1'
        try:
            action = int(action)
        except:
            CLIManagerClass.printout('> invalid selection\n')
            return
        # Mark the UI as busy while performing the requested operation.
        CLIManagerClass.update_status('BUSY')
        if action == 0:
            # Set a new root directory for repositories and refresh the list.
            self.__user_response_dir = True
            dir = self.input('Enter root directory for responsitories:\n')
            self.__user_response_dir = False
            self.repos.set_root_directory(dir)
            self.repos.refresh_repo_list()
            CLIManagerClass.clearout()
        if action == 1:
            # Refresh/check all repositories for changes.
            self.repos.refresh_repo_list()
        if action == 2:
            # Pull a specific subset of repositories chosen by the user.
            num_repos = self.repos.display_repos_to_pull()
            if num_repos < 1:
                self.repos.display_all_repos()
                return
            repo_list = []
            repo_list_str = ''
            repo_list_str = self.input('Enter repo numbers to pull separated by commas:\n')
            if repo_list_str == 'resetUI':
                self.repos.display_all_repos()
                return
            try:
                # Convert the user's comma-separated input into a list of
                # zero-based repo indices.
                repo_list = repo_list_str.split(',')
                count = 0
                for repo_id in repo_list:
                    repo_list[count] = int(repo_list[count])-1
                    count += 1
            except:
                repo_list = []
                self.repos.display_all_repos()
                return
            if len(repo_list) < 1:
                # No valid repos selected; show all repos and return.
                self.repos.display_all_repos()
                return
            self.repos.pull_some_repos(repo_list)
        if action == 3:
            # Pull all repositories.
            self.repos.pull_all_repos()
        # Display the full list of repositories after the operation.
        self.repos.display_all_repos()
        return
