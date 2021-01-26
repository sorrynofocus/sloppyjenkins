@echo off 
echo.
echo.

if NOT exist C:/Progra~1/Java/jdk1.7.0_55/lib/security/local_policy.jar (
    REM set CODECOVERAGEPROG=C:\Progra~2\BullseyeCoverage\bin
	REM copy 
	echo C:/Progra~1/Java/jdk1.7.0_55 does not exist!
	
) ELSE (
    REM set CODECOVERAGEPROG=C:\Progra~1\BullseyeCoverage\bin
	echo C:/Progra~1/Java/jdk1.7.0_55 does exist
)
echo.
echo Skipping default locations where java would be installed. Checking OPT_CM area...

if NOT exist C:\OPT_CM\java8\jre\lib\security\local_policy.jar (
    REM set CODECOVERAGEPROG=C:\Progra~2\BullseyeCoverage\bin
	echo C:\OPT_CM\java8\jre\lib\security\local_policy.jar does not exist!
	echo Java may not be installed if above not detected.
) ELSE (
    REM set CODECOVERAGEPROG=C:\Progra~1\BullseyeCoverage\bin
	echo C:\OPT_CM\java8\jre\lib\security\local_policy.jar does exist
	move C:\OPT_CM\java8\jre\lib\security\local_policy.jar C:\OPT_CM\java8\jre\lib\security\local_policy.bak 
	echo.
	echo Backing up C:\OPT_CM\java8\jre\lib\security\local_policy.bak
	
	move C:\OPT_CM\java8\jre\lib\security\US_export_policy.jar C:\OPT_CM\java8\jre\lib\security\US_export_policy.bak 
	echo.
	echo Backing up C:\OPT_CM\java8\jre\lib\security\US_export_policy.bak
	
	echo.
	echo Updating unlimited policy jars...
	
	copy M:\software\Java\UnlimitedJCEPolicyJDK8\*.jar C:\OPT_CM\java8\jre\lib\security
	
	echo.
	echo *** COMPLETE! ***
)

