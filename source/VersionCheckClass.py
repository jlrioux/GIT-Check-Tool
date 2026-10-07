
# VersionCheckClass.py
# Checks the GitHub releases page for GIT-Check-Tool and reports whether a
# newer release than the currently running version is available.
# Version strings use the format 'vMAJOR_MINOR_PATCH' (e.g. 'v1_3_0').

import urllib.request,re


# URL of the project's GitHub releases page
https_releases_url = 'https://github.com/jlrioux/GIT-Check-Tool/releases'
# Matches release anchors in the page HTML, e.g. "#release-v1_3_0",
# capturing the version number portion ('1_3_0')
regex_version_pattern = r'"#release-v(\d+_\d+_\d+)"'

class VersionCheckClass():
    # version: the currently running version string, e.g. 'v1_3_0'
    def __init__(self,version):
        self.__current_version = version

    # Returns True if new_version is newer than the current version,
    # otherwise False. Both are expected in 'vX_Y_Z' form.
    def __compare_versions(self,new_version):
        # Strip the 'v' prefix and split the current version into its parts
        version = self.__current_version.replace('v','')
        parts = version.split('_')

        # Same for the version found on GitHub
        nversion = new_version.replace('v','')
        nparts = nversion.split('_')

        # Walk through major, minor, patch in order; if any component of the
        # remote version is greater, report that an update is available.
        cur = 0
        for part in parts:
            if int(parts[cur]) < int(nparts[cur]):
                return True
            if int(parts[cur]) > int(nparts[cur]):
                return False
            cur += 1
        return False

    # Downloads the GitHub releases page, extracts the first (latest) release
    # version, and returns True if it is newer than the current version.
    # Returns False on any network error or if no version is found.
    def check_github_version(self):
        html = ''
        try:
            # use https_releases_url defined above.
            with urllib.request.urlopen(https_releases_url) as response:
                html = response.read().decode('utf-8')
        except:
            # Any failure (no network, HTTP error, etc.) is treated as "no update"
            return False
        # Find the first release anchor on the page (assumed to be the latest)
        match = re.search(regex_version_pattern,html)
        if not match:return False
        return self.__compare_versions(match.group(1))

