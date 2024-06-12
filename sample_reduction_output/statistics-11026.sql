CREATE TABLE a(b int4range PRIMARY KEY, c1 boolean) USING heap
    WITH(autovacuum_vacuum_cost_delay = 9, autovacuum_analyze_threshold = 0,
         autovacuum_analyze_scale_factor = 0.5);
CREATE TABLE t1(LIKE a);
CREATE TABLE IF NOT EXISTS t2(LIKE t1);
CREATE TABLE IF NOT EXISTS c(LIKE t2);
CREATE STATISTICS ON c1, b FROM c;
INSERT INTO c OVERRIDING USER VALUE VALUES('[-1958746335,5)' ::int4range, TRUE),
    ('(-1110737497,7]' ::int4range, FALSE);
ANALYZE;
SELECT(SELECT 0.7687387293646912 agg0 FROM c WHERE c.c1 UNION
           SELECT 0.7687387293646912 UNION SELECT MIN(0.7687387293646912)
               FROM c WHERE(c.c1) ISNULL);
