BEGIN TRANSACTION;
RAISERROR('base %s', 16, 1, DB_NAME());
UPDATE dbo.Clientes SET Activo = 0;
DELETE FROM dbo.Log;
DECLARE @n int = @@ROWCOUNT;
SELECT * FROM t WHERE id NOT IN (SELECT pid FROM u);
SELECT TOP 10 * FROM dbo.Ventas;
SELECT * FROM dbo.T WITH (NOLOCK);
DECLARE @a int = 1
IF @a > 0 THROW 50001, 'sin punto y coma antes', 1;
