CREATE  TABLE a(b TEXT   );
                            CREATE TABLE c(LIKE a);
                            CREATE TABLE d(LIKE c);
                            CREATE INDEX ON d (  (range_merge('(-745000293,62224459]'::int4range, '[399698862,1871382912]')));
                            UPDATE d SET b='/>ۼsjGmaꎑ' WHERE (b)LIKE(b);
