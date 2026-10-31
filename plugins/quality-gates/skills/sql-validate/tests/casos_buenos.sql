SET NOCOUNT ON;
SET XACT_ABORT ON;
DECLARE @base sysname = DB_NAME();
IF @base NOT LIKE '%QAS%'
BEGIN
    RAISERROR('base "%s" incorrecta.', 16, 1, @base);
    RETURN;
END
BEGIN TRY
    BEGIN TRANSACTION;
    DECLARE @n int;
    UPDATE dbo.T SET c = 1 WHERE id = 5;
    SET @n = @@ROWCOUNT;
    IF @n <> 1
       OR @n IS NULL
        THROW 51001, 'conteo inesperado', 1;
    DELETE FROM #tmp;
    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH

/* UPDATE STATISTICS no es DML: es mantenimiento del optimizador y nunca lleva
   WHERE. Disparaba `update-sin-where` como falso positivo (2026-08-24). */
UPDATE STATISTICS dbo.VersionCotizacion WITH FULLSCAN;

-- MERGE con predicado largo en el WHEN y borrado por NOT MATCHED BY SOURCE.
-- Ni el UPDATE ni el DELETE llevan WHERE, y no pueden llevarlo: los acotan la
-- clausula ON y los predicados de cada WHEN. Un validador que marque esto
-- marca todo MERGE correcto.
MERGE dbo.Destino AS T
USING (SELECT Id, A, B, C FROM dbo.Carga) AS S
    ON T.Id = S.Id
WHEN MATCHED AND (
        ISNULL(T.A, 255) <> ISNULL(S.A, 255)
     OR T.B              <> S.B
     OR ISNULL(T.C, -1)  <> ISNULL(S.C, -1)
) THEN UPDATE SET
    T.A = S.A,
    T.B = S.B,
    T.C = S.C
WHEN NOT MATCHED BY TARGET THEN
    INSERT (Id, A, B, C) VALUES (S.Id, S.A, S.B, S.C)
WHEN NOT MATCHED BY SOURCE THEN DELETE;
