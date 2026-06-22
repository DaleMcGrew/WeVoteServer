# Debugging Fast Load with the Master and the Local being the same instance

Start with a "Plain" database backup from the master server, if you don't have access to the Production pgAdmin 4 instance ask Steve or Dale to get you the file.
In this example the file is named ....  `wevoteApiDbPlainJun19-230pm`  (As of June 2026, this file is 40 to 50GB -- This is the full database, including disposable cache files, FastLoad copies a subset of these tables.)

The schema for the Master server has to match the schema for the local, otherwise the backup file will not load.  So make sure your backup file is current.

Use the pgAdmin4, **Tools | Storage Manager** to download the file to your Mac (downloading this 50GB file can take a half hour or more).

You want to get the file in to the weconnect-db, so copy the file to `/tmp/docker` on your local, and it will be accessible at `/tmp` in a weconnect-db shell.


1) In a terminal, open a shell in the db container: `docker compose exec db sh`
2) Drop the existing database:
    `DROP DATABASE wevoteserverdb WITH (FORCE);`
3) Recreate the database:
    `CREATE DATABASE wevoteserverdb;`
4) Populate the database from the database backup file (this can take a half hour or more minutes to complete):
    `psql -X -f /tmp/wevoteApiDbPlainJun19-230pm  "wevoteserverdb"`

```
stevepodell@Steves-MBP-M1-Dec2021 WeVoteServer % docker compose exec db sh
/ $ bash
85fb778ebdb9:/$ psql
psql (16.14)
Type "help" for help.

postgres=# DROP DATABASE wevoteserverdb WITH (FORCE);
DROP DATABASE
postgres=# CREATE DATABASE wevoteserverdb;
CREATE DATABASE
postgres=# \q
85fb778ebdb9:/$ psql -X -f /tmp/wevoteApiDbPlainJun19-230pm  "wevoteserverdb"
psql: error: /tmp/wevoteApiDbPlainJun19-230pm: No such file or directory
85fb778ebdb9:/$ ls -la /tmp
total 8
drwxrwxrwt    1 root     root          4096 Jun 16 17:55 .
drwxr-xr-x    1 root     root          4096 Jun 11 21:20 ..
85fb778ebdb9:/$ 
What's next:
    Debug this Compose error with Gordon → docker ai "help me fix this compose error"
stevepodell@Steves-MBP-M1-Dec2021 WeVoteServer % docker compose exec db sh
/ $ bash
65253e894fa2:/$ psql
psql (16.14)
Type "help" for help.

postgres=# \l
                                                         List of databases
      Name      |  Owner   | Encoding | Locale Provider |  Collate   |   Ctype    | ICU Locale | ICU Rules |   Access privileges   
----------------+----------+----------+-----------------+------------+------------+------------+-----------+-----------------------
 postgres       | postgres | UTF8     | libc            | en_US.utf8 | en_US.utf8 |            |           | 
 template0      | postgres | UTF8     | libc            | en_US.utf8 | en_US.utf8 |            |           | =c/postgres          +
                |          |          |                 |            |            |            |           | postgres=CTc/postgres
 template1      | postgres | UTF8     | libc            | en_US.utf8 | en_US.utf8 |            |           | =c/postgres          +
                |          |          |                 |            |            |            |           | postgres=CTc/postgres
 wevoteserverdb | postgres | UTF8     | libc            | en_US.utf8 | en_US.utf8 |            |           | 
(4 rows)

postgres=# DROP DATABASE wevoteserverdb WITH (FORCE);
DROP DATABASE
postgres=# CREATE DATABASE wevoteserverdb;
CREATE DATABASE
postgres=# CREATE ROLE rdsadmin WITH SUPERUSER LOGIN PASSWORD 'admin';
CREATE ROLE
postgres=# CREATE ROLE dbadmin WITH SUPERUSER LOGIN PASSWORD 'admin';
CREATE ROLE
postgres=# \q
65253e894fa2:/$ ls -la /tmp
total 20836
drwxr-xr-x   15 postgres postgres       480 Jun 16 17:49 .
drwxr-xr-x    1 root     root          4096 Jun 16 17:59 ..
-rw-r--r--    1 postgres postgres      6148 Jun 16 17:49 .DS_Store
-rw-r--r--    1 postgres postgres    442478 Jun 12 20:48 Person.tsv
-rw-r--r--    1 postgres postgres      1272 Jun 12 20:48 PersonAway.tsv
-rw-r--r--    1 postgres postgres    444312 Jun 12 20:48 QuestionAnswer.tsv
-rw-r--r--    1 postgres postgres      1073 Jun 12 20:48 Questionnaire.tsv
-rw-r--r--    1 postgres postgres      8268 Jun 12 20:48 QuestionnaireQuestion.tsv
-rw-r--r--    1 postgres postgres    790826 Jun 12 20:48 Task.tsv
-rw-r--r--    1 postgres postgres     64369 Jun 12 20:48 TaskDefinition.tsv
-rw-r--r--    1 postgres postgres      5761 Jun 12 20:48 TaskGroup.tsv
-rw-r--r--    1 postgres postgres      1245 Jun 12 20:48 TaskGroupTeamLink.tsv
-rw-r--r--    1 postgres postgres      3770 Jun 12 20:48 Team.tsv
-rw-r--r--    1 postgres postgres     83716 Jun 12 20:48 TeamMember.tsv
-rw-r--r--    1 postgres postgres  19444487 Jun 16 17:26 wevoteApiDbPlainJun19-230pm
drwxr-xr-x    3 postgres postgres        96 Jun 10 16:18 node-compile-cache
65253e894fa2:/$ psql -X -f /tmp/wevoteApiDbPlainJun19-230pm  "wevoteserverdb"
SET
SET
...
GRANT
GRANT
65253e894fa2:/$ 
```
Those "CREATE ROLE" lines are only necessary the first time you import the database from pgAdmin, or if you have wiped the db with `docker compose down -v`, so otherwise you can
skip them, or ignore the errors.

Set the environment variable that uses the local server as a master and local
```
  "DEBUG_FASTLOAD_SINGLE_SERVER":   true,
```


**Be sure to undo these temporary before checkin in your code or FastLoad will not work for other developers.**

Every time you want to re-run fastload with a fresh database, you will need to repeat these steps.

[//]: # (Recreate the DevUser after every database drop/create &#40;or re-running docker compose up handles this automatically&#41;)
[//]: # (```)
[//]: # (stevepodell@Steves-MBP-M1-Dec2021 WeVoteServer % docker compose exec api sh)
[//]: # ($ bash)
[//]: # (wevote@ffd6fad9f9ac:/wevote/code$ python manage.py create_dev_user Samuel Adams samuel@adams.com ale)
[//]: # (Creating developer first name=Samuel, last name=Adams, email=samuel@adams.com, password =ale)
[//]: # (End of create_dev_user)
[//]: # (wevote@ffd6fad9f9ac:/wevote/code$ )
[//]: # (# )
[//]: # (```)

### Testing pg_dump
This shows a docker package version mismatch, which hopefully will never occur again
The logged symptoms were: `retrieve_tables.controllers_local: pg_restore failed: pg_restore: error: input file is too short (read 0, expected 5)`
```
wevote@a8d5e48e95f6:/wevote/code$ pg_dump postgresql://postgres:admin@db:5432/wevoteserverdb --table=position_positionentered --format=c --file=/tmp/steve1
pg_dump: error: aborting because of server version mismatch
pg_dump: detail: server version: 16.14; pg_dump version: 15.18 (Debian 15.18-0+deb12u1)
wevote@a8d5e48e95f6:/wevote/code$ 
```

## See Listeners

```
wevote@8b5c7b9adc9c:/wevote/code$ ss
Netid            State            Recv-Q             Send-Q                         Local Address:Port                          Peer Address:Port             Process            
tcp              ESTAB            0                  0                                  127.0.0.1:49384                            127.0.0.1:55281                               
tcp              ESTAB            0                  0                                  127.0.0.1:55281                            127.0.0.1:49384                               
tcp              ESTAB            0                  0                                  127.0.0.1:55281                            127.0.0.1:49404                               
tcp              ESTAB            0                  0                                 172.18.0.5:8000                          192.168.65.1:45249                               
tcp              ESTAB            0                  0                                  127.0.0.1:49404                            127.0.0.1:55281                               
tcp              ESTAB            0                  0                                  127.0.0.1:55281                            127.0.0.1:49398                               
tcp              ESTAB            0                  0                                  127.0.0.1:49398                            127.0.0.1:55281                               
tcp              ESTAB            0                  0                                 172.18.0.5:8000                          192.168.65.1:65517                               
wevote@8b5c7b9adc9c:/wevote/code$ 
```