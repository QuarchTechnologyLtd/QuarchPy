@echo off
rem start /b javaw -jar qis.jar -terminal
start /b javaw -Djava.net.preferIPv4Stack=true -Djava.net.preferIPv6Addresses=false -jar qis.jar
