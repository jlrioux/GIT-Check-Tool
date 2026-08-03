
import os,sys,time,json,subprocess

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

settings = {'root dir':None}
data = {'action id':-1,
        'repo dir list':[],
        'repos with pulls':[],
        'repos with commits':[]}

cwd = os.getcwd()

def get_settings_from_file():
    global settings
    try:
        with open(cwd+'/settings.json','r') as file:
            settings = json.load(file)
    except:
        pass

def __save_root_dir():
    settings['root dir'] = input('Enter root directory for responsitories:')
    if len(settings['root dir']) > 0:
        settings['root dir'] = settings['root dir'].replace('\\','/')
        while settings['root dir'][-1] in ['/']:
            settings['root dir'] = settings['root dir'][:-1]
    with open(cwd+'/settings.json','w') as file:
        json.dump(settings,file)

def __build_repo_list(dir=''):
    if not dir:
        data['repo dir list'] = []
        dir = settings['root dir']
    dir_list = os.listdir(dir)
    if '.git' in dir_list:
        data['repo dir list'].append(dir)
        print('---- repo directory found:'+dir)
        return
    else:
        for item in dir_list:
            __build_repo_list(dir+'/'+item)

def __build_update_list():
    data['repos with pulls'] = []
    data['repos with commits'] = []
    count = 0
    for dir in data['repo dir list']:
        print('Checking repository {}/{} for updates:{}'.format(count+1,len(data['repo dir list']),dir))
        os.chdir(dir)
        subprocess.run(['git','fetch'], capture_output=True, text=True, check=True)
        result = subprocess.run(['git','status'], capture_output=True, text=True, check=True)
        if 'Your branch is up to date with' not in result.stdout:
            print(bcolors.FAIL+'---- outstanding PULL found for repo:'+dir+bcolors.ENDC)
            data['repos with pulls'].append(dir)
        if 'nothing to commit,' not in result.stdout:
            print(bcolors.FAIL+'---- outstanding COMMIT for repo:'+dir+bcolors.ENDC)
            data['repos with commits'].append(dir)
        count += 1
    print('{} respositories need to be PULLED'.format(len(data['repos with pulls'])))
    print('{} respositories need to be COMMITTED, this must be done manually'.format(len(data['repos with commits'])))

def __list_repos_with_pulls():
    if len(data['repos with pulls']) < 1:
        print('---- no repositories to pull')
        return
    count = 0
    for dir in data['repos with pulls']:
        print('    {}. {}'.format(count,dir))
        count += 1
    repo_list = []
    while not repo_list:
        try:
            repo_list = input('Enter repo numbers to pull separated by commas:')
            repo_list = repo_list.split(',')
            count = 0
            for repo_id in repo_list:
                repo_list[count] = int(repo_list[count])
                count += 1
        except:
            repo_list = []
            print('---- invalid repo list')
    for repo_id in repo_list:
        __pull_repo(data['repos with pulls'][repo_id])
        data['repos with pulls'].remove(dir)

def __pull_repo(dir):
    print('---- pulling repo:'+dir)
    os.chdir(dir)
    result = subprocess.run(['git','pull'], capture_output=True, text=True, check=True)
    print(bcolors.OKGREEN+'---- pull result:\n{}'.format(result.stdout)+bcolors.ENDC)

def __pull_all_repos():
    if len(data['repos with pulls']) < 1:
        print('---- no repositories to pull')
        return
    for dir in data['repos with pulls']:
        __pull_repo(dir)
    data['repos with pulls'] = []

def process_input():
    if settings['root dir'] == None:
        __save_root_dir()
        return
    if settings:
        print('\nRepositories root directory:'+settings['root dir'])
    action = input("""
    0. Set root directory for repositories
    1. List repository directories
    2. Check all repositories for changes
    3. Pull for certain repositories
    4. Pull for all repositories
    5. Quit
    What would you like to do? :""")
    try:
        action = int(action)
    except:
        print('invalid selection')
        return
    data['action id'] = action
    if action == 0:
        __save_root_dir()
    if action == 1:
        __build_repo_list()
    if action == 2:
        __build_repo_list()
        __build_update_list()
    if action == 3:
        __list_repos_with_pulls()
    if action == 4:
        __pull_all_repos()
    if action == 5:
        sys.exit()
    return












get_settings_from_file()
while(True):
    time.sleep(0.5)
    process_input()