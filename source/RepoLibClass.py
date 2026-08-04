import os,json,subprocess
from concurrent.futures import ThreadPoolExecutor

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

cwd = os.getcwd()

def run_git_command(repo_uid, command):
    repo = RepoManager.repos[repo_uid]
    if hasattr(repo,command):
        getattr(repo,command)()


class RepoManager():
    repos = {} #type:dict[int,RepoClass]
    def __init__(self):
        self.root_directory_set = False
        self.__settings = {'root dir':None}
        self.__dir_list = []
        self.__next_uid = 0
        self.__repos_sorted = []
        self.get_settings_from_file()
        if self.__settings['root dir']:
            self.__build_repo_list()
            self.__remove_deleted_repos()
    
    def get_settings_from_file(self):
        try:
            with open(cwd+'/settings.json','r') as file:
                self.__settings = json.load(file)
                self.root_directory_set = True
                self.refresh_repo_list()
                self.display_all_repos()
        except:
            pass

    def set_root_directory(self,dir):
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
        if not dir:
            self.__dir_list = []
            dir = self.__settings['root dir']
        dir_list = os.listdir(dir)
        if '.git' in dir_list:
            self.__dir_list.append(dir)
            #print('---- repo directory found:'+dir)
            self.__create_repo(dir)
            return
        else:
            for item in dir_list:
                self.__build_repo_list(dir+'/'+item)

    def __create_repo(self,dir):
        #check if repo already exists
        for repo in self.__repos_sorted:
            repo = repo[1]
            if repo.dirpath == dir:
                return
        self.repos[self.__next_uid] = RepoClass(self.__next_uid,dir)
        self.repos[self.__next_uid].subscribe(self.__create_repo_status_handler())
        self.__repos_sorted = sorted(self.repos.items(), key=lambda item:item[1])
        self.__next_uid += 1

    def __remove_deleted_repos(self):
        repos_to_remove = []
        for repo in self.__repos_sorted:
            repo = repo[1]
            if repo.dirpath not in self.__dir_list:
                repos_to_remove.append(repo.uid)
        for uid in repos_to_remove:
            del self.repos[uid]
        self.__repos_sorted = sorted(self.repos.items(), key=lambda item:item[1])

    def __create_repo_status_handler(self):
        def h(uid,pull_status,push_status):
            print('UPDATE:uid={}:pull status={}:push status={}'.format(uid,pull_status,push_status))

    def pull_all_repos(self):
        repo_uids = []
        for uid in self.repos.keys():
            if self.repos[uid].vpull_available:
                repo_uids.append(uid)
        with ThreadPoolExecutor(max_workers=len(repo_uids)) as executor:
            futures = {executor.submit(run_git_command, repo_uid, 'execute_pull'): repo_uid for repo_uid in repo_uids}

    def pull_some_repos(self,id_list):
        uid_list = []
        txt = ""
        count = 1
        for repo in self.__repos_sorted:
            repo = repo[1]
            if repo.vpull_available:
                if count in id_list:
                    uid_list.append(count)
                count += 1

        repo_uids = []
        for uid in uid_list:
            if uid in self.repos.keys():
                if self.repos[uid].vpull_available:
                    repo_uids.append(uid)
                else:print('---- no pull for {}')
            else:print('---- {} not in the list')
        with ThreadPoolExecutor(max_workers=len(repo_uids)) as executor:
            futures = {executor.submit(run_git_command, repo_uid, 'execute_pull'): repo_uid for repo_uid in repo_uids}

    def refresh_repo_list(self):
        print('Building Repo List')
        self.__build_repo_list()
        self.__remove_deleted_repos()
        print('Checking Repo Status')
        self.force_all_repo_status_query()

    def __create_repo_display_text(self,repo):
        txt = '"{}" status: '.format(repo.dirpath)
        if not repo.vpush_available and not repo.vpull_available:
            txt += bcolors.OKGREEN + 'GOOD' + bcolors.ENDC
        elif repo.vpush_available and repo.vpull_available:
            txt += bcolors.FAIL + 'PULL' + bcolors.ENDC +', ' + bcolors.WARNING + 'PUSH' + bcolors.ENDC
        elif not repo.vpush_available and repo.vpull_available:
            txt += bcolors.FAIL + 'PULL' + bcolors.ENDC
        elif repo.vpush_available and not repo.vpull_available:
            txt += bcolors.WARNING + 'PUSH' + bcolors.ENDC
        return txt

    def display_all_repos(self):
        txt = ""
        count = 1
        pull_count = 0
        push_count = 0
        for repo in self.__repos_sorted:
            repo = repo[1]
            txt += '\n{}. {}'.format(count,self.__create_repo_display_text(repo))
            if repo.vpush_available:push_count += 1
            if repo.vpull_available:pull_count += 1
            count += 1
        print(txt)
        print('{} repositories need to be pushed'.format(push_count))
        print('{} repositories need to be pulled'.format(pull_count))

    def display_repos_to_pull(self):
        txt = ""
        count = 1
        pull_count = 0
        for repo in self.__repos_sorted:
            repo = repo[1]
            if repo.vpull_available:
                pull_count += 1
                txt += '\n{}. {}'.format(count,self.__create_repo_display_text(repo))
                count += 1
        print(txt)
        print('{} repositories need to be pulled'.format(pull_count))
        return pull_count

    def force_all_repo_status_query(self):
        repo_uids = []
        for repo in self.__repos_sorted:
            repo_uids.append(repo[0])
            
        with ThreadPoolExecutor(max_workers=len(repo_uids)) as executor:
            futures = {executor.submit(run_git_command, repo_uid, 'refresh_status'): repo_uid for repo_uid in repo_uids}

class RepoClass():

    def __init__(self,uid,dirpath):
        self.dirpath = dirpath
        self.uid = uid
        self.vpull_available = False
        self.vpush_available = False
        self.vbusy = False

        self.__status_updated_callback = False

    #operator overloading
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

    def subscribe(self,func):
        self.__status_updated_callback = func

    def refresh_status(self):
        self.vbusy = True
        #os.chdir(self.dirpath)
        fetch_command = 'git -C "{}" fetch'.format(self.dirpath)
        subprocess.run(fetch_command, shell=True, capture_output=True, text=True, check=True)
        #subprocess.run(['git','fetch'], capture_output=True, text=True, check=True)
        status_command = 'git -C "{}" status'.format(self.dirpath)
        result = subprocess.run(status_command, shell=True, capture_output=True, text=True, check=True)
        #result = subprocess.run(['git','status'], capture_output=True, text=True, check=True)
        if 'Your branch is up to date with' not in result.stdout:
            self.vpull_available = True
        else:
            self.vpull_available = False
        if 'nothing to commit,' not in result.stdout:
            self.vpush_available = True
        else:
            self.vpush_available = False
        self.vbusy = False
        if self.__status_updated_callback:
            self.__status_updated_callback(self.uid,self.vpull_available,self.vpush_available)

    def execute_pull(self):
        self.vbusy = True
        print('---- pulling repo:'+self.dirpath)
        pull_command = 'git -C "{}" pull'.format(self.dirpath)
        result = subprocess.run(pull_command, shell=True, capture_output=True, text=True, check=True)
        print('---- pulling complete:'+self.dirpath)
        print(bcolors.OKGREEN+'---- pull result:\n{}'.format(result.stdout)+bcolors.ENDC)
        self.refresh_status()

