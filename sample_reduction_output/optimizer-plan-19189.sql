 CREATE TABLE a(b int4range ) ;
                         CREATE TABLE c(LIKE a);
                         SELECT BOOL_AND(b-|-b) FROM c;
