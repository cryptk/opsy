from functools import partial
from opsy.access import Need


MonitoringNeed = partial(Need, 'monitoring')  # pylint: disable=invalid-name

# Dashboards
dashboards_read = MonitoringNeed(  # pylint: disable=invalid-name
    'dashboards_read', 'Ability to list/show dashboards in the API.')
# Zones
zones_read = MonitoringNeed('zones_read',  # pylint: disable=invalid-name
                            'Ability to list/show zones in the API.')
# Events
events_read = MonitoringNeed('events_read',  # pylint: disable=invalid-name
                             'Ability to list/show events in the API.')
# Checks
checks_read = MonitoringNeed('checks_read',  # pylint: disable=invalid-name
                             'Ability to list/show checks in the API.')
# Results
results_read = MonitoringNeed('results_read',  # pylint: disable=invalid-name
                              'Ability to list/show results in the API.')
# Silences
silences_read = MonitoringNeed('silences_read',  # pylint: disable=invalid-name
                               'Ability to list/show silences in the API.')
# Clients
clients_read = MonitoringNeed('clients_read',  # pylint: disable=invalid-name
                              'Ability to list/show clients in the API.')

monitoring_needs = [  # pylint: disable=invalid-name
    dashboards_read, zones_read, events_read, checks_read, results_read,
    silences_read, clients_read
]
