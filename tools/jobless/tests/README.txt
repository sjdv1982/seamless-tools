Cleaning the database:

use "seamless-delete-database-from-log jobless-test-dblog.txt"
 to clean up buffers, transformation results etc. from the database.
This forces jobless to re-execute the jobs rather than 
 plucking them from the database.

jobless-test-dblog-ORIGINAL.txt is jobless-test-dblog.txt 
 when all tests are run in the order: bash, docker_, parse-pdb, simple, compiled, autodock.
Use this if you have misplaced or scrambled your own jobless-test-dblog.txt 