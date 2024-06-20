CREATE TABLE a(g TEXT, b REAL, c FLOAT);
CREATE TABLE d(LIKE a);
CREATE TABLE e(LIKE d);
CREATE TABLE f(LIKE e);
CREATE INDEX ON e(('(8,045]' ::int4range));
SELECT f.g, e.g, f.c, f.b FROM f CROSS JOIN e UNION SELECT f.g, e.g, f.c,
    f.b FROM f CROSS JOIN e UNION SELECT f.g, e.g, f.c,
    f.b FROM f CROSS JOIN e WHERE(e.g) IS NULL;
