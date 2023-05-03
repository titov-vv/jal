# FAQ

1. *Which platforms/operation systems are supported by JAL*?  
JAL was created as a cross-platform appication based on *python* and GUI library *[Qt](https://www.qt.io/)*.
Thus, theoretically, it should work on any platform that supports python and Qt installation.  
Installation and usage were tested on Linux, Windows and MacOS systems. 
But there are some problematic enviroments sometimes, like Windows with ARM (M1) CPU (*JAL* can't be installed due to *numpy* library compilation failure).

2. *Application does not start from python! We're write in it `>>>pip install jal`, and got SyntaxError*.  
JAL must run not from interactive python shell but, as any other python script, by passing a name of running program to python interpreter as an argument. It's shown in examples in Readme. 

3. *How to start from begining, with clean database*?   
You may use menu _Data -> Clean All_ to start from scratch.  
Or you may delete JAL database file manually (don't forget to make backup if needed!). Database file is named `jal/jal.sqlite`. If you delete it (while programm is closed, sure), next run JAL creates new, clean database.
