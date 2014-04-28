In order to test the Downloads viz you need to install the database:

    7zip x cp_downloads_AutomatorTest.sql.7z 
    mysqladmin -u root create cp_downloads_AutomatorTest
    mysql -u root cp_downloads_AutomatorTest < cp_downloads_AutomatorTest.sql

Add

    db_downloads = cp_downloads_AutomatorTest

to main.conf in automator project and you are done.
