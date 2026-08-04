import sys,time
from RepoLibClass import RepoManager

repos = RepoManager()




def process_input():
    if not repos.root_directory_set:
        dir = input('Enter root directory for responsitories:')
        repos.set_root_directory(dir)
        return
    action = input("""
    0. Set root directory for repositories
    1. Check all repositories for changes
    2. Pull for certain repositories
    3. Pull for all repositories
    4. Quit
What would you like to do? :""")
    try:
        action = int(action)
    except:
        print('invalid selection')
        return
    if action == 0:
        dir = input('Enter root directory for responsitories:')
        repos.set_root_directory(dir)
    if action == 1:
        repos.refresh_repo_list()
        repos.display_all_repos()
    if action == 2:
        num_repos = repos.display_repos_to_pull()
        if num_repos < 1:return
        repo_list = []
        while not repo_list:
            try:
                repo_list = input('Enter repo numbers to pull separated by commas:')
                repo_list = repo_list.split(',')
                count = 0
                for repo_id in repo_list:
                    repo_list[count] = int(repo_list[count])-1
                    count += 1
            except:
                repo_list = []
                print('---- invalid repo list')
        repos.pull_some_repos(repo_list)
    if action == 3:
        repos.pull_all_repos()
    if action == 4:
        sys.exit()
    return


while(True):
    time.sleep(0.5)
    process_input()