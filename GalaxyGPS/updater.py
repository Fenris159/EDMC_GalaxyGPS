import json
import logging
import os
import traceback
import zipfile

from config import appname, user_agent  # type: ignore
import timeout_session  # type: ignore

# We need a name of plugin dir, not GalaxyGPS.py dir
plugin_name = os.path.basename(os.path.dirname(os.path.dirname(__file__)))
logger = logging.getLogger(f'{appname}.{plugin_name}')


class SpanshUpdater():
    def __init__(self, version, plugin_dir):
        self.version = version
        self.zip_name = "EDMC_GalaxyGPS_" + version.replace('.', '') + ".zip"
        self.plugin_dir = plugin_dir
        self.zip_path = os.path.join(self.plugin_dir, self.zip_name)
        self.zip_downloaded = False
        self.changelogs = self.get_changelog()

    def download_zip(self):
        # GitHub repository configuration
        github_repo = "Fenris159/EDMC_GalaxyGPS"  # Format: "username/repository"
        
        # Release tag on GitHub is the version string without "v" (e.g. 1.5.1 not v1.5.1)
        url = f'https://github.com/{github_repo}/releases/download/{self.version}/{self.zip_name}'
        logger.info(f"GalaxyGPS update: fetching {url}")

        try:
            session = timeout_session.new_session()
            session.headers['User-Agent'] = user_agent + ' GalaxyGPS'
            r = session.get(url, timeout=60)
            if r.status_code == 200:
                with open(self.zip_path, 'wb') as f:
                    f.write(r.content)
                logger.info(f"GalaxyGPS update: downloaded to {self.zip_path}")
                self.zip_downloaded = True
            else:
                logger.warning(f"GalaxyGPS update: download failed status={r.status_code} url={url}")
                self.zip_downloaded = False
        except Exception:
            logger.warning('!! ' + traceback.format_exc(), exc_info=False)
            self.zip_downloaded = False
        
        return self.zip_downloaded

    def install(self):
        # Use existing zip if already downloaded (e.g. pre-downloaded when user clicked Install)
        zip_ready = os.path.isfile(self.zip_path)
        if not zip_ready:
            zip_ready = self.download_zip()
        if zip_ready:
            try:
                with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                    zip_ref.extractall(self.plugin_dir)
                os.remove(self.zip_path)
                logger.info("GalaxyGPS update extracted successfully")
            except Exception:
                logger.warning('!! ' + traceback.format_exc(), exc_info=False)
        else:
            logger.warning("Error when downloading the latest GalaxyGPS update")

    def get_changelog(self):
        # GitHub repository configuration
        github_repo = "Fenris159/EDMC_GalaxyGPS"  # Format: "username/repository"
        
        url = f"https://api.github.com/repos/{github_repo}/releases/latest"
        try:
            session = timeout_session.new_session()
            session.headers['User-Agent'] = user_agent + ' GalaxyGPS'
            r = session.get(url, timeout=2)
            if r.status_code == 200:
                # Get the changelog and replace all breaklines with simple ones
                changelogs = json.loads(r.content)["body"]
                changelogs = "\n".join(changelogs.splitlines())
                return changelogs

        except Exception:
            logger.warning('!! ' + traceback.format_exc(), exc_info=False)
        return None
