"""
State module for restconf Proxy minions

:codeauthor: Jamie (Bear) Murphy <jamiemurphyit@gmail.com>
:maturity:   new
:platform:   any

About
=====
This state module was designed to manage restconf states.
This module relies on the restconf proxy module to interface with the devices.
"""


import json
import logging

# from salt.utils.odict import OrderedDict

try:
    HAS_DEEPDIFF = True
    from deepdiff import DeepDiff
except ImportError:
    HAS_DEEPDIFF = False

log = logging.getLogger(__file__)


def __virtual__():
    if not HAS_DEEPDIFF:
        return (
            False,
            "Missing dependency: The restconf states method requires the 'deepdiff' Python module.",
        )
    if "restconf.set_data" in __salt__:
        return True
    return (False, "restconf module could not be loaded")


def config_manage(name, uri, method, config, init_uri=None, init_method="PATCH"):
    """
    Ensure a specific value exists at a given path

    name:
        (str) The name for this rule

    uri:
        (str) The restconf uri to set / get config

    method:
        (str) rest method to use eg GET, PUT, POST, PATCH, DELETE

    config:
        (dict) The new value at the given path

    init_uri: (optional)
        (str) Alternative URI incase the URI doesnt exist on first pass

    init_method: (optional)
        (str) Method to use on alternative URI when setting config, default: PATCH

    Examples:

    .. code-block:: yaml

        do_configure_restconf_endpoint:
          restconf.config_manage:
            - name: random_name_here
            - uri: restconf/data/Cisco-IOS-XE-native:native/interface/GigabitEthernet=1%2F0%2F3
            - config:
                Cisco-IOS-XE-native:GigabitEthernet:
                  description: interfaceDescription
                  name: "1/0/3"

    """

    uri = str(uri)
    name = str(name)
    method = str(method)
    if uri == "":
        log.critical("uri must not be blank")
        return False
    if name == "":
        log.critical("Name is required")
        return False
    if method == "":
        log.critical("method is required")
        return False
    if not type(config) is dict:
        log.critical("config is required, config must be a dict")
        return False

    # TODO: add template function so that config var does not need to be passed
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}
    found_working_uri = False
    uri_used = ""
    existing_raw = __salt__["restconf.get_data"](uri)
    request_uri = ""
    request_method = ""
    # TODO: this could probaby be a loop
    if existing_raw["status"] in [200]:
        existing = existing_raw["dict"]
        found_working_uri = True
        uri_used = "Primary"
        request_uri = uri
        request_method = method

    if not found_working_uri:
        existing_raw_init = __salt__["restconf.get_data"](init_uri)
        if existing_raw_init["status"] in [200]:
            existing = existing_raw_init["dict"]
            found_working_uri = True
            uri_used = "init"
            request_uri = init_uri
            request_method = init_method

    if not found_working_uri:
        ret["result"] = False
        ret["comment"] = "restconf could not find a working URI to get initial config"
        return ret
    # TODO: END

    dict_config = json.loads(
        json.dumps(config)
    )  # convert from orderedDict to Dict (which is now ordered by default in python3.8)

    if existing == dict_config:
        ret["result"] = True
        ret["comment"] = "Config is already set"

    elif __opts__["test"] is True:
        ret["result"] = None
        ret["comment"] = "Config will be added"
        diff = _restDiff(existing, dict_config)
        ret["changes"]["new"] = diff.added()
        ret["changes"]["removed"] = diff.removed()
        ret["changes"]["changed"] = diff.changed()

    else:
        resp = __salt__["restconf.set_data"](request_uri, request_method, dict_config)
        # Success
        if resp["status"] in [201, 200, 204]:
            ret["result"] = True
            ret["comment"] = "Successfully added config"
            diff = _restDiff(existing, dict_config)
            ret["changes"]["new"] = diff.added()
            ret["changes"]["removed"] = diff.removed()
            ret["changes"]["changed"] = diff.changed()
            if method == "PATCH":
                ret["changes"]["removed"] = None
        # full failure
        else:
            ret["result"] = False
            if "dict" in resp:
                why = resp["dict"]
            elif "body" in resp:
                why = resp["body"]
            else:
                why = None
            ret[
                "comment"
            ] = "failed to add / modify config. API Statuscode: {s}, API Response: {w}, URI:{u}".format(
                w=why, s=resp["status"], u=uri_used
            )
            print("post_content: {b}".format(b=json.dumps(dict_config)))

    return ret


class _restDiff:
    """
    Calculate the difference between two dictionaries as:
    (1) items added
    (2) items removed
    (3) keys same in both but changed values
    (4) keys same in both and unchanged values
    """

    def __init__(self, current_dict, past_dict):
        self.current_dict = current_dict
        self.past_dict = past_dict
        self.diff = DeepDiff(current_dict, past_dict)
        print("DeepDiff:")
        print(self.diff)
        self.diff_pretty = self.diff.pretty()

    def added(self):
        # TODO: Potential for new adds to get missed here.
        # need to dig into deepdiff more
        if "dictionary_item_added" in self.diff.keys():
            return str(self.diff["dictionary_item_added"])
        return None

    def removed(self):
        if "dictionary_item_removed" in self.diff.keys():
            return str(self.diff["dictionary_item_removed"])
        return None

    def changed(self):
        if "values_changed" in self.diff.keys():
            return str(self.diff["values_changed"])
        return None

    def unchanged(self):
        return None  # TODO: not implemented