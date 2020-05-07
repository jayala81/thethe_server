import json
import traceback
import json
import urllib.request

from tasks.api_keys import KeyRing
from server.entities.resource_types import ResourceType
from tasks.tasks import celery_app
from server.entities.plugin_manager import PluginManager
from server.entities.plugin_result_types import PluginResultStatus


# Which resources are this plugin able to work with
RESOURCE_TARGET = [ResourceType.IPv4]

# Plugin Metadata {a description, if target is actively reached and name}
PLUGIN_AUTOSTART = True
PLUGIN_DESCRIPTION = "Use a GeoIP service to geolocate an IP address"
PLUGIN_DISABLE = False
PLUGIN_IS_ACTIVE = False
PLUGIN_NAME = "geoip"
PLUGIN_NEEDS_API_KEY = False

API_KEY = KeyRing().get("ipstack")
API_KEY_IN_DDBB = bool(API_KEY)
API_KEY_DOC = "https://ipstack.com/signup/free"
API_KEY_NAMES = ["ipstack"]


class Plugin:
    def __init__(self, resource, project_id):
        self.project_id = project_id
        self.resource = resource

    def do(self):
        resource_type = self.resource.get_type()

        try:
            to_task = {
                "ip": self.resource.get_data()["address"],
                "resource_id": self.resource.get_id_as_string(),
                "project_id": self.project_id,
                "resource_type": resource_type.value,
                "plugin_name": PLUGIN_NAME,
            }
            geoip.delay(**to_task)

        except Exception as e:
            tb1 = traceback.TracebackException.from_exception(e)
            print("".join(tb1.format()))


@celery_app.task
def geoip(plugin_name, project_id, resource_id, resource_type, ip):
    result_status = PluginResultStatus.STARTED
    result = None

    try:
        API_KEY = KeyRing().get("ipstack")
        if not API_KEY:
            print("No API key...!")
            return None

        URL = f"http://api.ipstack.com/{ip}?access_key={API_KEY}&format=1"
        response = urllib.request.urlopen(URL).read()

        result = json.loads(response)
        if "success" in result:
            if not result["success"]:
                if result["error"]["code"] in [101, 102, 103, 104, 105]:
                    result_status = PluginResultStatus.NO_API_KEY
                elif result["error"]["code"] == 404:
                    result_status = PluginResultStatus.RETURN_NONE
        else:
            result_status = PluginResultStatus.COMPLETED

            PluginManager.set_plugin_results(
                resource_id, plugin_name, project_id, result, result_status
            )

    except Exception as e:
        tb1 = traceback.TracebackException.from_exception(e)
        print("".join(tb1.format()))
        return None
