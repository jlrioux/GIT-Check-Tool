# RepoLibClass.py
# ================
# Git repository management helper library for the GIT-Check-Tool.
# This module provides two core classes:
#   - RepoManager: Discovers Git repositories under a root directory,
#     queries their status, triggers pull operations (multi-threaded),
#     sends Windows toast notifications, and tracks the overall
#     push/pull state of the workspace.
#   - RepoClass: Represents a single Git repository, storing its path,
#     unique id, push/pull availability flags, and busy state. It also
#     provides operator overloads used for sorting and status queries.

import os,json,subprocess
from win11toast import toast
from concurrent.futures import ThreadPoolExecutor


# Current working directory, used as the base for locating settings.json.
cwd = os.getcwd()

def run_git_command(repo_uid, command):
    # Dispatch a named command to a repository instance.
    # This is used as the worker target for the ThreadPoolExecutor,
    # allowing multiple repositories to be processed in parallel.
    # repo_uid: unique id of the target repository.
    # command : name of the method to invoke on the RepoClass object.
    repo = RepoManager.repos[repo_uid]
    if hasattr(repo,command):
        getattr(repo,command)()


class RepoManager():
    # Manager class that oversees all discovered Git repositories.
    # Responsibilities include:
    #   - Discovering repos under a configured root directory
    #   - Persisting/loading settings from settings.json
    #   - Querying repo status (push/pull availability)
    #   - Triggering pull operations using a thread pool
    #   - Sending Windows toast notifications for new pulls
    #   - Providing a summary of the overall workspace state

    repos = {} #type:dict[int,RepoClass]  # uid -> RepoClass mapping
    printout = None        # callback used to print messages to the UI
    update_status = None   # callback used to update the global status indicator
    def __init__(self,printout,update_status,allow_toast):
        # Initialize the manager with UI callbacks and settings.
        RepoManager.printout = printout
        RepoManager.update_status = update_status
        self.root_directory_set = False  # becomes True once a root dir is configured/loaded
        self.current_status = 'BUSY'     # current overall status of all repos
        self.__settings = {'root dir':None}  # persisted app settings
        self.__dir_list = []             # list of dirs that contain a .git (repos)
        self.__next_uid = 0              # counter for assigning unique repo ids
        self.__repos_sorted = []         # repos sorted by dirpath (list of (uid,repo) tuples)
        self.__pull_repo_list = []       # pull repos already notified (for toast tracking)
        self.__dismiss_toasts = False    # flag to stop sending further toasts
        self.allow_toasts = allow_toast  # whether toast notifications are enabled
        self.get_settings_from_file()
        if self.__settings['root dir']:
            RepoManager.printout('> Building Repo List\n')
            self.__build_repo_list()
            self.__remove_deleted_repos()

    def send_toast(self,title,content):
        # Send a Windows toast notification with 'View' and 'Dismiss All' buttons.
        # Returns the arguments of the clicked button, or '' if none.
        res = toast(title, 
            content,
            audio={'silent': 'true'},
            buttons=['View','Dismiss All'],
            on_dismissed=self.__handle_toast_dismissed())
        try:
            return res['arguments']
        except:
            return ''
    def __handle_toast_dismissed(self):
        # Callback factory for toast dismissal events (currently a no-op).
        def h(reason):
            pass
        return h
    def __check_toast(self):
        # Compare current pull-available repos against the previously notified ones,
        # and send a toast for each newly available repo (unless dismissed).
        pull_list = []
        notify_list = []
        self.update_current_status()
        if not self.allow_toasts:return
        for repo in self.__repos_sorted:
            repo = repo[1]
            if repo.vpull_available:
                pull_list.append(repo)
        for repo in pull_list:
            if repo not in self.__pull_repo_list:
                notify_list.append(repo)
        self.__pull_repo_list = pull_list
        count = 1
        self.__dismiss_toasts = False
        for repo in notify_list:
            if self.__dismiss_toasts == False:
                res = self.send_toast('New Repo Pull',
                        '{}/{}\n"{}"'.format(count,len(notify_list),repo.dirpath)
                        )
                if 'View' in res:
                    self.__dismiss_toasts = True
                    RepoManager.update_status('SHOW WINDOW')
                elif 'Dismiss' in res:
                    self.__dismiss_toasts = True
            count += 1
        

    def get_settings_from_file(self):
        # Load settings from settings.json; on success, refresh the repo list
        # and display all repos. Silently ignores a missing/invalid settings file.
        try:
            with open(cwd+'/settings.json','r') as file:
                self.__settings = json.load(file)
                self.root_directory_set = True
                self.refresh_repo_list()
                self.display_all_repos()
        except:
            pass

    def set_root_directory(self,dir):
        # Store the chosen root directory, normalize separators, persist it to
        # settings.json, then rebuild the repo list and display the results.
        self.__settings['root dir'] = dir
        if len(self.__settings['root dir']) > 0:
            self.__settings['root dir'] = self.__settings['root dir'].replace('\\','/')
            while self.__settings['root dir'][-1] in ['/']:
                self.__settings['root dir'] = self.__settings['root dir'][:-1]
        with open(cwd+'/settings.json','w') as file:
            json.dump(self.__settings,file)
        self.root_directory_set = True
        self.refresh_repo_list()
        self.display_all_repos()

    def __build_repo_list(self,dir=''):
        # Recursively walk the root directory. Any folder containing a '.git'
        # entry is treated as a repository and added to the repo list.
        if not dir:
            self.__dir_list = []
            dir = self.__settings['root dir']
        if not os.path.isdir(dir):return
        dir_list = os.listdir(dir)
        if '.git' in dir_list:
            self.__dir_list.append(dir)
            self.__create_repo(dir)
            return
        else:
            for item in dir_list:
                self.__build_repo_list(dir+'/'+item)

    def __create_repo(self,dir):
        # Create a RepoClass for a discovered repo, skipping it if it already exists.
        for repo in self.__repos_sorted:
            repo = repo[1]
            if repo.dirpath == dir:
                return
        self.repos[self.__next_uid] = RepoClass(self.__next_uid,dir)
        self.__repos_sorted = sorted(self.repos.items(), key=lambda item:item[1])
        self.__next_uid += 1

    def __remove_deleted_repos(self):
        # Remove repos whose directory is no longer part of the discovered list.
        repos_to_remove = []
        for repo in self.__repos_sorted:
            repo = repo[1]
            if repo.dirpath not in self.__dir_list:
                repos_to_remove.append(repo.uid)
        for uid in repos_to_remove:
            del self.repos[uid]
        self.__repos_sorted = sorted(self.repos.items(), key=lambda item:item[1])

    def pull_all_repos(self):
        # Pull every repo that has updates available, using a thread pool.
        repo_uids = []
        for uid in self.repos.keys():
            if self.repos[uid].vpull_available:
                repo_uids.append(uid)
        if len(repo_uids) < 1:return
        with ThreadPoolExecutor(max_workers=len(repo_uids)) as executor:
            futures = {executor.submit(run_git_command, repo_uid, 'execute_pull'): repo_uid for repo_uid in repo_uids}
        self.__check_toast()

    def pull_some_repos(self,id_list):
        # Pull only the repos selected by the given indices (as displayed in the list).
        uid_list = []
        count = 0
        for repo in self.__repos_sorted:
            if repo[1].vpull_available:
                if count in id_list:
                    uid_list.insert(0,repo[0])
                count += 1

        repo_uids = []
        for uid in uid_list:
            if uid in self.repos.keys():
                if self.repos[uid].vpull_available:
                    repo_uids.append(uid)
                else:RepoManager.printout('> ---- no pull for {}\n'.format(self.repos[uid].dirpath))
            else:RepoManager.printout('> ---- {} not in the list\n'.format(self.repos[uid].dirpath))
        if len(repo_uids) < 1:return
        with ThreadPoolExecutor(max_workers=len(repo_uids)) as executor:
            futures = {executor.submit(run_git_command, repo_uid, 'execute_pull'): repo_uid for repo_uid in repo_uids}
        self.__check_toast()

    def push_repo(self,id_list,commit_message):
        # Push only the repos selected by the given indices (as displayed in the list).
        uid_list = []
        count = 0
        for repo in self.__repos_sorted:
            if repo[1].vpush_available:
                if count in id_list:
                    uid_list.insert(0,repo[0])
                count += 1

        repo_uids = []
        uid = uid_list[0]
        if uid in self.repos.keys():
            if self.repos[uid].vpush_available:
                repo_uids.append(uid)
            else:RepoManager.printout('> ---- no push for {}\n'.format(self.repos[uid].dirpath))
        else:RepoManager.printout('> ---- {} not in the list\n'.format(self.repos[uid].dirpath))
        if len(repo_uids) < 1:return
        self.repos[uid].execute_push(commit_message)
        self.__check_toast()

    def refresh_repo_list(self):
        # Rebuild the repo list from disk, remove stale repos, and re-query status.
        RepoManager.printout('> Building Repo List\n')
        self.__build_repo_list()
        self.__remove_deleted_repos()
        self.force_all_repo_status_query()

    def __create_repo_display_text(self,repo):
        # Print the status text for a single repo with color coding.
        RepoManager.printout('"{}" Status: '.format(repo.dirpath))
        if not repo.vpush_available and not repo.vpull_available:
            RepoManager.printout('GOOD','green')
        elif repo.vpush_available and repo.vpull_available:
            RepoManager.printout('PULL','red')
            RepoManager.printout(' / ')
            RepoManager.printout('PUSH','orange')
        elif not repo.vpush_available and repo.vpull_available:
            RepoManager.printout('PULL','red')
        elif repo.vpush_available and not repo.vpull_available:
            RepoManager.printout('PUSH','orange')

    def display_all_repos(self):
        # Print a numbered list of all repos with their status, plus summary counts.
        txt = ""
        count = 1
        pull_count = 0
        push_count = 0
        for repo in self.__repos_sorted:
            RepoManager.printout('> ')
            RepoManager.printout('{}. '.format(count))
            repo = repo[1]
            self.__create_repo_display_text(repo)
            RepoManager.printout('\n')
            if repo.vpush_available:push_count += 1
            if repo.vpull_available:pull_count += 1
            count += 1
        RepoManager.printout('> {} repositories need to be pushed\n'.format(push_count))
        RepoManager.printout('> {} repositories need to be pulled\n'.format(pull_count))

    def update_current_status(self):
        # Compute the global status (GOOD/PUSH/PULL/BOTH) across all repos and report it.
        push_needed = 0
        pull_needed = 0
        results = {0:'GOOD',1:'PUSH',2:'PULL',3:'BOTH'}
        for repo in self.__repos_sorted:
            repo = repo[1]
            if repo.vpush_available:push_needed = 1
            if repo.vpull_available:pull_needed = 2
        result = push_needed + pull_needed
        self.current_status = results[result]
        RepoManager.update_status(self.current_status)

    def display_repos_to_pull(self):
        # Print a numbered list of repos that have updates available to pull.
        count = 1
        pull_count = 0
        for repo in self.__repos_sorted:
            repo = repo[1]
            if repo.vpull_available:
                RepoManager.printout('> ')
                RepoManager.printout('{}. '.format(count))
                self.__create_repo_display_text(repo)
                RepoManager.printout('\n')
                pull_count += 1
                count += 1
        if pull_count > 0:
            RepoManager.printout('> {} repositories need to be pulled\n'.format(pull_count))
        return pull_count

    def display_repos_to_push(self):
        # Print a numbered list of repos that have updates available to push.
        count = 1
        push_count = 0
        for repo in self.__repos_sorted:
            repo = repo[1]
            if repo.vpush_available:
                RepoManager.printout('> ')
                RepoManager.printout('{}. '.format(count))
                self.__create_repo_display_text(repo)
                RepoManager.printout('\n')
                push_count += 1
                count += 1
        if push_count > 0:
            RepoManager.printout('> {} repositories need to be pushed\n'.format(push_count))
        return push_count

    def force_all_repo_status_query(self):
        # Refresh the status of every repo in parallel using a thread pool.
        repo_uids = []
        for repo in self.__repos_sorted:
            repo_uids.append(repo[0])
        RepoManager.printout('> Checking Repo Status\n')
        with ThreadPoolExecutor(max_workers=len(repo_uids)) as executor:
            futures = {executor.submit(run_git_command, repo_uid, 'refresh_status'): repo_uid for repo_uid in repo_uids}
        self.__check_toast()

class RepoClass():
    # Represents a single Git repository, tracking its push/pull availability,
    # busy state, and providing the ability to query status and pull.

    def __init__(self,uid,dirpath):
        self.dirpath = dirpath
        self.uid = uid
        self.vpull_available = False
        self.vpush_available = False
        self.vstatus = 'GOOD'

        self.vbusy = False

    #operator overloading
    # Comparison operators are overridden so repos can be sorted by their dirpath.
    def __eq__(self,other):
        return self.dirpath == other.dirpath
    def __ne__(self,other):
        return self.dirpath != other.dirpath
    def __lt__(self,other):
        return self.dirpath < other.dirpath
    def __le__(self,other):
        return self.dirpath <= other.dirpath
    def __gt__(self,other):
        return self.dirpath > other.dirpath
    def __ge__(self,other):
        return self.dirpath >= other.dirpath

    def refresh_status(self):
        # Fetch and check the repo status via git, then update push/pull flags.
        self.vbusy = True
        fetch_command = 'git -C "{}" fetch'.format(self.dirpath)
        try:
            result = subprocess.check_output(fetch_command, shell=True, text=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as cpe:
            RepoManager.printout('> ---- status fetch failed: "' + self.dirpath + '"\n{}'.format(str(cpe.output)) + '\n','red')
            RepoManager.printout('> {}\n'.format(e))
            return
        except Exception as e:
            RepoManager.printout('> ---- status fetch failed: "'+self.dirpath,'red')
            RepoManager.printout('> {}\n'.format(e))
            return
        status_command = 'git -C "{}" status'.format(self.dirpath)
        
        try:
            result = subprocess.check_output(status_command, shell=True, text=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as cpe:
            RepoManager.printout('> ---- status fetch failed: "' + self.dirpath + '"\n{}'.format(str(cpe.output)) + '\n','red')
            RepoManager.printout('> {}\n'.format(e))
            return
        except Exception as e:
            RepoManager.printout('> ---- status fetch failed: "'+self.dirpath,'red')
            RepoManager.printout('> {}\n'.format(e))
            return
        if 'Your branch is up to date with' not in result:
            self.vpull_available = True
        else:
            self.vpull_available = False
        if 'nothing to commit,' not in result:
            self.vpush_available = True
        else:
            self.vpush_available = False
        self.vbusy = False
        new_status = self.__check_status()
        status_changed = self.vstatus == new_status
        self.vstatus = new_status

    def execute_pull(self):
        # Run git pull on this repo, print the result, and refresh the status.
        self.vbusy = True
        RepoManager.printout('> ---- pulling repo:'+self.dirpath+'\n')
        pull_command = 'git -C "{}" pull'.format(self.dirpath)
        try:
            #result = subprocess.run(pull_command, shell=True, capture_output=True, text=True, check=True)
            result = subprocess.check_output(pull_command, shell=True, text=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as cpe:
            RepoManager.printout('> ---- pulling failed: "' + self.dirpath + '"\n{}'.format(str(cpe.output)) + '\n','red')
            RepoManager.printout('> {}\n'.format(cpe))
            return
        except Exception as e:
            RepoManager.printout('> ---- pulling failed: "'+self.dirpath,'red')
            RepoManager.printout('> {}\n'.format(e))
            return
        RepoManager.printout('> ---- pulling complete:'+self.dirpath+'\n')
        RepoManager.printout('> ')
        RepoManager.printout('pull result:\n{}\n'.format(result),'green')
        self.refresh_status()

    def execute_push(self,commit_message):
        # Run git pull on this repo, print the result, and refresh the status.
        self.vbusy = True
        RepoManager.printout('> ---- pushing repo:'+self.dirpath+'\n')
        push_command = 'git -C "{}" add -A && git -C "{}" commit -m "{}" && git -C "{}" push'.format(self.dirpath,self.dirpath,commit_message,self.dirpath)
        try:
            result = subprocess.check_output(push_command, shell=True, text=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as cpe:
            RepoManager.printout('> ---- pushing failed: "' + self.dirpath + '"\n{}'.format(str(cpe.output)) + '\n','red')
            RepoManager.printout('> {}\n'.format(cpe))
            return
        except Exception as e:
            RepoManager.printout('> ---- pushing failed: "'+self.dirpath,'red')
            RepoManager.printout('> {}\n'.format(e))
            return
        RepoManager.printout('> ---- pushing complete:'+self.dirpath+'\n')
        RepoManager.printout('> ')
        RepoManager.printout('push result:\n{}\n'.format(result),'green')
        self.refresh_status()

    def __check_status(self):
        # Combine push/pull flags into an overall status string.
        push_needed = 0
        pull_needed = 0
        results = {0:'GOOD',1:'PUSH',2:'PULL',3:'BOTH'}
        if self.vpush_available:push_needed = 1
        if self.vpull_available:pull_needed = 2
        result = push_needed + pull_needed
        return results[result]
