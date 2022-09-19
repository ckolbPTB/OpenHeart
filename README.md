# OpenHeart

![overview](https://user-images.githubusercontent.com/17784338/191044136-603a519c-81ce-4e96-bd47-a3d0fc78d338.png)

## Installation
You need to have `docker` as well as `docker-compose` installed.
All other requirements will be installed into the docker container where the application is running.

## Developing OpenHeart
The current setup in the Dockerfile runs `RUN pip install -e .` and mounts the current directory into the `/app` directory.
This means while you develop the application locally it will automatically update inside the docker container and you don't need to rebuild the image or stop the container. The app will re-start automatically upon storing changes to the source code. (Caveat: this means you should not change the code while you use the app or wait for an upload etc.)

This of course only includes changes to the app. Python packages you add to the `requirements.txt` will require a new build of the image of course.

## Usage
To start the app run
```
docker-compose up
```
and the image should build from Dockerfile if it is not already existing. If you need to rebuild the image you have to run `docker-compose up --build`.
The `docker-compose` command picks up information on volumes and ports from the `docker-compose.yml` file.

Afterwards the app can be accessed on port 5001 of the machine it is started on. In Dockerfile the line `CMD ["python3", "-m", "flask", "run", "--host=0.0.0.0", "--port=5001"]` defines the host and port numbers.

## Building the reconstruction container for the XNAT server
ToDo

## Testing
For running the tests two things are required:

- **Setup of Test XNAT projects:** In the file `tests/conftest.py` the dictionary `test_app_configuration` defines the parameters passed to the app in the test configuration. The keys 'XNAT_SERVER'
'XNAT_ADMIN_USER', 'XNAT_ADMIN_PW', 'XNAT_PROJECT_ID_VAULT' and 'XNAT_PROJECT_ID_OPEN' must point to an existing XNAT server and projects that are dedicated to testing.
- **Supplying of test data:** To run the tests inside the running docker container the you need to mount a folder (in the following called TESTPATH) to `/test` in the container where some data are available to run the tests. The current tests require to supply the substructure `/test/input/dicoms` where some dicoms should be stored and `/test/output` where the tests store some files.
**Important:** TESTPATH must not be a vagrant-synchronised folder (i.e. a shared folder) cause zip extraction will not work in them.

Since the app runs in a container the container must be started before executing `pytest`.
Probably there is a smarter way incorporating the `docker-compose.yml` for this but manually starting up the container and running the pytest works. 
```
docker run -v $(pwd)/:/app -v sql_volume:/logs -v sql_volume:/db -v data_volume:/data -v temp_volume:/temp -v /home/sirfuser/XNATTestData:/test -it openheart_app /bin/bash -c "python3 -m pytest -s"
```
(The command above does not expose ports yet, potentially for testing email sending from the app the option `-p 465:465` is required.)
