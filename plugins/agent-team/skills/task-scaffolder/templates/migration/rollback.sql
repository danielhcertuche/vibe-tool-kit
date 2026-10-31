-- --- artifact metadata ---
-- owner_agent: {{OWNER_AGENT}}
-- upstream:    {{UPSTREAM}}
-- downstream:  {{DOWNSTREAM}}
-- created_at:  {{CREATED_AT}}
-- template:    task-scaffolder/migration
-- ---

-- Rollback: {{NAME}}
-- DANGER: Run only to undo the corresponding skeleton.sql migration.

BEGIN TRANSACTION;

IF EXISTS (
    SELECT 1 FROM sys.tables WHERE name = '{{NAME}}'
)
BEGIN
    -- TODO: implement rollback DDL here
    -- Example:
    -- DROP TABLE [dbo].[{{NAME}}];
    PRINT 'Rollback {{NAME}} applied.';
END
ELSE
BEGIN
    PRINT 'Table {{NAME}} does not exist — rollback skipped.';
END

COMMIT TRANSACTION;
