# Care TeleICU Devices Plugin

Care plugin for TeleICU Gateway, ONVIF Camera, HL7 Vitals Observation Device device integration.

> [!NOTE] 
> This plugin package consists of three plugs:
> 1. `gateway_device` - This plug is responsible for gateway device integration such as TeleICU Gateway. This is required for camera and vitals observation device plugs to work.
> 2. `camera_device` - This plug is responsible for camera device integration such as ONVIF cameras.
> 3. `vitals_observation_device` - This plug is responsible for vitals observation device such as HL7 Monitor / Ventilator.

## Local Development

To develop the plug in local environment along with care, follow the steps below:

1. Go to the care root directory and clone the plugin repository:

```bash
cd care
git clone git@github.com:ohcnetwork/care_teleicu_devices.git
```

2. Add the following plug configuration to your `plug_config.py` file to enable the plugins locally:

```python
from plugs.manager import PlugManager
from plugs.plug import Plug

plugs = [
    Plug(
        name="gateway_device",
        package_name="/path/to/care_teleicu_devices", # for local development, point this to the absolute path to the cloned plug repository
        version="",
        configs={},
    ),
    Plug(
        name="camera_device",
        package_name="/path/to/care_teleicu_devices", # for local development, point this to the absolute path to the cloned plug repository
        version="",
        configs={},
    ),
    Plug(
        name="vitals_observation_device",
        package_name="/path/to/care_teleicu_devices", # for local development, point this to the absolute path to the cloned plug repository
        version="",
        configs={},
    ),
]

manager = PlugManager(plugs)
```

3. Tweak the code in plugs/manager.py to update the pip install command with the -e flag for editable installation

```python
subprocess.check_call(
    [sys.executable, "-m", "pip", "install", "-e", *packages] # add -e flag to install in editable mode
)
```

> [!IMPORTANT]
> Do not push these changes in a PR. These changes are only for local development.

4. Install the plugins

```bash
python install_plugins.py
```

5. Rebuild the docker image and run the server

```bash
make re-build
make up
```

## Production Setup

To install care teleicu devices plugs, you can add the plugin config in [care/plug_config.py](https://github.com/ohcnetwork/care/blob/develop/plug_config.py) as follows:

```python
from plugs.manager import PlugManager
from plugs.plug import Plug

plugs = [
    Plug(
        name="gateway_device",
        package_name="git+https://github.com/ohcnetwork/care_teleicu_devices.git",
        version="@main",
        configs={},
    ),
    Plug(
        name="camera_device",
        package_name="git+https://github.com/ohcnetwork/care_teleicu_devices.git",
        version="@main",
        configs={},
    ),
    Plug(
        name="vitals_observation_device",
        package_name="git+https://github.com/ohcnetwork/care_teleicu_devices.git",
        version="@main",
        configs={},
    ),
]

manager = PlugManager(plugs)
```

[Extended Docs on Plug Installation](https://care-be-docs.ohc.network/pluggable-apps/configuration.html)

## License

This project is licensed under the terms of the [MIT license](LICENSE).

---

This plugin was created with [Cookiecutter](https://github.com/audreyr/cookiecutter) using the [ohcnetwork/care-plugin-cookiecutter](https://github.com/ohcnetwork/care-plugin-cookiecutter).
