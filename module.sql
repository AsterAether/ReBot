DELIMITER //
DROP FUNCTION IF EXISTS phash_distance //
CREATE FUNCTION phash_distance(p_hash1 CHAR(16), p_hash2 CHAR(16))
  RETURNS FLOAT
DETERMINISTIC
  BEGIN
    DECLARE count INT;
    DECLARE i INT;
    DECLARE L CHAR(2);
    DECLARE R CHAR(2);
    DECLARE N INT;

    SET i = 0;
    SET count = 0;

    REPEAT
      SET L = SUBSTR(p_hash1, 1 + i * 2, 2);
      SET R = SUBSTR(p_hash2, 1 + i * 2, 2);
      SET N = CONV(L, 16, 10) ^ CONV(R, 16, 10);
      SET count = count + bit_count(N);
      SET i = i + 1;
    UNTIL i = 8
    END REPEAT;
    RETURN 1 - count / 64.0;
  END //
DROP PROCEDURE IF EXISTS get_post_per_distance //
CREATE PROCEDURE get_post_per_distance(p_hash CHAR(16), p_chat_id INTEGER, p_threshold FLOAT)
DETERMINISTIC
  BEGIN
    DROP TABLE IF EXISTS tmp_post_per_distance;
    CREATE TEMPORARY TABLE tmp_post_per_distance AS
      SELECT
        *,
        phash_distance(file_hash, p_hash)         AS distance,
        phash_distance(file_preview_hash, p_hash) AS distance_preview
      FROM post
      WHERE (chat_id = p_chat_id OR chat_id IS NULL) AND
                                   (phash_distance(file_hash, p_hash) >= p_threshold OR
                                    phash_distance(file_preview_hash, p_hash) >= p_threshold)
      ORDER BY distance, distance_preview;
    COMMIT;
  END //
DROP PROCEDURE IF EXISTS get_repost_per_distance //
CREATE PROCEDURE get_repost_per_distance(p_hash CHAR(16), p_chat_id INTEGER, p_threshold FLOAT)
DETERMINISTIC
  BEGIN
    DROP TABLE IF EXISTS tmp_repost_per_distance;
    CREATE TEMPORARY TABLE tmp_repost_per_distance AS
      SELECT
        *,
        phash_distance(file_hash, p_hash)         AS distance,
        phash_distance(file_preview_hash, p_hash) AS distance_preview
      FROM repost
      WHERE (chat_id = p_chat_id OR chat_id) IS NULL AND
                                   (phash_distance(file_hash, p_hash) >= p_threshold OR
                                    phash_distance(file_preview_hash, p_hash) >= p_threshold)
      ORDER BY distance, distance_preview;
    COMMIT;
  END //
DELIMITER ;