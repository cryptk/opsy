import asyncio
import importlib
from hourglass.backends import db


class UwsgiScheduler(object):

    def __init__(self, app):
        self.app = app
        self.loop = asyncio.get_event_loop()
        self.interval = int(app.config['hourglass'].get(
            'scheduler_interval', 30))
        self.zones = self._load_zones()

    def _load_zones(self):
        zones = []
        for name, config in self.app.config['zones'].items():
            backend = config.get('backend')
            package = backend.split(':')[0]
            class_name = backend.split(':')[1]
            zone_module = importlib.import_module(package)
            zone_class = getattr(zone_module, class_name)
            host = config.get('host')
            port = config.get('port')
            timeout = int(config.get('timeout', 10))
            zones.append(zone_class(name, host, port, timeout))
        return zones

    def create_cache_db(self):
        with self.app.app_context():
            db.drop_all(bind='cache')
            db.create_all(bind='cache')
            db.session.bulk_save_objects(self.zones)
            db.session.commit()

    def run_tasks(self, kill_loop=False):
        with self.app.app_context():
            tasks = []
            for zone in self.zones:
                tasks.extend(zone.get_update_tasks(self.app, self.loop))
            results = self.loop.run_until_complete(asyncio.gather(*tasks))
            for result in results:
                db.session.bulk_save_objects(result)
            db.session.commit()
            self.app.logger.info('Cache database updated')
        if kill_loop:
            self.loop.close()