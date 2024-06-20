CREATE TABLE a(b smallint, c DECIMAL);
CREATE TABLE d(LIKE a);
INSERT INTO a(c) VALUES(0.7228929725659718);
INSERT INTO d(c) VALUES(0.5251311333230952), (0.3962654665536074);
INSERT INTO a(c) VALUES(0.25702960088398363);
SELECT a.b, a.c, d.b,
    d.c FROM a JOIN d ON(d.c) BETWEEN SYMMETRIC(d.c) AND
        0 WHERE(a.c) >= 0 UNION ALL SELECT a.b,
    a.c, d.b, d.c FROM a JOIN d ON 0 >= 0 UNION ALL SELECT a.b, a.c, d.b,
    d.c FROM a JOIN d ON NULL;
