#!/bin/bash
java -Djava.net.preferIPv4Stack=true -Djava.net.preferIPv6Addresses=false -Djava.awt.headless=true -jar ./qis.jar
# run in background after closing cmd window ?
#nohup java -Djava.awt.headless=true -jar ./qis.jar &
# run in background after closing cmd window logging output to file ?
#nohup java -Djava.awt.headless=true -jar ./qis.jar > qis.log &
