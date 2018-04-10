CREATE FUNCTION phash_distance(phash1 VARCHAR(16), phash2 VARCHAR(16))
  RETURNS INTEGER
  BEGIN
    DECLARE hex1part1 BIGINT;
    DECLARE hex1part2 BIGINT;

    DECLARE hex2part1 BIGINT;
    DECLARE hex2part2 BIGINT;

    SET hex1part1 = CONV(SUBSTRING(phash1, 1, 8), 16, 10);
    SET hex1part2 = CONV(SUBSTRING(phash1, 8, 8), 16, 10);

    SET hex2part1 = CONV(SUBSTRING(phash2, 1, 8), 16, 10);
    SET hex2part2 = CONV(SUBSTRING(phash2, 8, 8), 16, 10);
    RETURN bit_count(hex1part1 ^ hex2part1) + bit_count(hex1part2 ^ hex2part2);
  END;

DROP FUNCTION phash_distance;

SELECT phash_distance('af8dda9220b4c8db', 'afcdfa006c1f02f2')
FROM dual;

SELECT SUBSTRING('af8dda9220b4c8db', 1, 8)
FROM dual;

SELECT
  CONV(SUBSTRING('af8dda9220b4c8db', 1, 8), 16, 10) + CONV(SUBSTRING('af8dda9220b4c8db', 1, 8), 16, 10) AS one,
  CONV('af8dda9220b4c8db', 16, 10)
FROM dual;

SELECT 1- (bit_count(0x8fdbd850f32da051 ^ 0xac53d872732dd053) / 64)
FROM dual;