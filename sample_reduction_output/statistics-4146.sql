CREATE TABLE a(b int4range, c boolean);
CREATE TABLE d(LIKE a);
CREATE TABLE e(LIKE d);
CREATE TABLE f(LIKE e);
CREATE STATISTICS ON c, b FROM f;
INSERT INTO f VALUES('[4,7)');
ANALYZE;
SELECT MIN(0.7687387293646912) FROM f WHERE(c) ISNULL;
