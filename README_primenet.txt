primenet.py: An automatic assignment handler for Mlucas.
This handles LL and PRP testing (first-time and double-check), i.e. all the worktypes supported by the program.
Support for computer registration and assignment-progress via direct Primenet-v5-API calls by Loïc Le Loarer <loic@le-loarer.org>.

This script is intended to be run alongside Mlucas - use it to register your computer (if you've not previously done so)
and then reinvoke in periodic-update mode to automatically fetch work from the Primenet server, report latest results and
report the status of currently-in-progress assignments to the server, which you can view in a convenient dashboard form via
login to the server and clicking Account/Team Info --> My Account --> CPUs. (Or directly via URL: https://www.mersenne.org/cpus/)

Note: primenet.py should support python versions from 2.6 to 3.9.

primenet.py should be run in the same directory as Mlucas binary and they both work together like this:
o primenet.py will get new assignments if necessary and append to worktodo.ini file
o Mlucas reads the worktodo.ini file and runs the first assignment
o Mlucas outputs the results in results.txt file and remove the first line for worktodo.ini when done
o primenet.py sends the results from results.txt and place them in results_send.txt to not send them twice.

To register your computer, you have to launch primenet.py with --register option at least once:
	$ ./primenet.py --register --username [uid] --password [pwd]
Currently, only the hostname is automatically detected, if you want to give hardware details from your computer, you can add the corresponding options like this (this is correct for a RaspberryPi4 2GB):
	$ ./primenet.py --register --cpu_model "ARM Cortex A-72" --features "asimd" --frequency "1500" --L1 32 --L2 512 --memory 2000 --np 4 --hp 0
You can see those informations by clicking on the corresponding CPU in the cpus page on mersenne.org (https://www.mersenne.org/cpus/).

primenet.py saves command-line options in the local.ini file, so that you only have to give them once.
So once you've done the initial computer-registration step, you don't need to repeat your username and password in
subsequent invocations of the script. (If your computer is online all the time or at least part of each day, you
should only need to invoke in periodic-update (daemon) mode right after your computer boots up, then you can forget it.)

You can also modifiy the local.ini file by hand to change the options.
You can relaunch primenet.py with the --register option at any time to update your computer details with mersenne.org.

After the initial computer-registration step, you should run primenet.py in foreground (not as a daemon) at least once to check that it works correctly. Here -d enables debug-printing, it is recommended to always use this flag, even when
running in background (daemon) mode, in which case invoking the script using 'nohup' diverts all logging to the nohup.out text file:
	$ ./primenet.py -d -t 0

If everything is right, the result should be a non-empty worktodo.ini file and you can launch Mlucas.

Then, if you have an always-on or even occasionally-on internet connection, you can run primenet.py as a daemon so that worktodo and result are automatically updated and progress regularly send to mersenne.org. The command line to use is the following:
	$ ./primenet.py -d
Use whatever method is the best for you to run a daemon, like nohup. If you don't know how to do, you should try the systemd method described below.

Several options can be usefull to adapt the primenet.py behavior:
o -T to chose the worktype (double-check LL by default)
o -t (or --timeout) to chose the frequency of updates (6 hours by default)
o -n (or --num_cache) to tell how many assignments to cache. One more assignment will automatically by obtained if the current estimated time left is smalller than the 3*timeout or when the percentage of completion of the current assignment exceed percent_limit so that you should never run out of assignment even if num_cache is 1 (the default)
o -L (or --percent_limit) to get one more assignment when the current has reach the given percentage.

Additionally, here is a tip to run primenet.py and mlucas as a daemon using systemd.
Just create a unit file in /etc/systemd/system/primenet.service
with a content similar to this one (remove the tab-indents and adapt the file paths and user name):
	-------------------------
	[Unit]
	Description=MLucas GIMPS primenet
	After=network.target

	[Service]
	WorkingDirectory=/home/pi/mlucas/run0
	ExecStart=/home/pi/mlucas/primenet.py -d
	Type=simple
	User=pi
	Restart=on-failure

	[Install]
	WantedBy=default.target
	-------------------------
And for mlucas, create a unit file in /etc/systemd/system/mlucas.service
with a content similar to this one (adapt the file paths, user name and Mlucas options):
	-------------------------
	[Unit]
	Description=MLucas GIMPS
	After=network.target

	[Service]
	WorkingDirectory=/home/pi/mlucas/run0
	ExecStart=/home/pi/mlucas/Mlucas_c2simd -cpu 0:3
	StandardOutput=file:/home/pi/mlucas/run0/output.log
	StandardError=file:/home/pi/mlucas/run0/output.log
	Type=simple
	User=pi
	Restart=on-failure

	[Install]
	WantedBy=default.target
	-------------------------
Reload systemd with
	$ sudo systemctl daemon-reload
And run the daemons
	$ sudo systemctl start primenet
	$ sudo systemctl start mlucas
Then you can see the status of the script and its output:
	$ sudo systemctl status primenet

If you created several working directory (for example, one per core), then, you can create only one systemd unit file using the @ to match the variable part.
Suppose you have created several run0, run1, run2... directories, create a /etc/systemd/system/primenet@.service file, and use %I inside to match the variable part like this:
	-------------------------
	[Unit]
	Description=MLucas GIMPS primenet
	After=network.target

	[Service]
	WorkingDirectory=/home/pi/mlucas/run%I
	ExecStart=/home/pi/mlucas/primenet.py -d
	Type=simple
	User=pi
	Restart=on-failure

	[Install]
	WantedBy=default.target
	-------------------------
Then, you can control the job using the following commands:
	$ systemctl start primenet@0 primenet@1 primenet@2...
The same applies to mlucas unit file.

This version dated 7 July 2020.
