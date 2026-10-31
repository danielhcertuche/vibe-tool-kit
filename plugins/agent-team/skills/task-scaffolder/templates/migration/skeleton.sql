-- --- artifact metadata ---
-- owner_agent: {{OWNER_AGENT}}
-- upstream:    {{UPSTREAM}}
-- downstream:  {{DOWNSTREAM}}
-- created_at:  {{CREATED_AT}}
-- template:    task-scaffolder/migration
-- ---

-- Migration: {{NAME}}
-- Description: <describe what this migration does>

BEGIN TRANSACTION;

-- Guard: skip if already applied
IF NOT EXISTS (
    SELECT 1 FROM sys.tables WHERE name = '{{NAME}}'
)
BEGIN
    -- TODO: implement migration DDL here
    -- Example:
    -- CREATE TABLE [dbo].[{{NAME}}] (
    --     [id]         INT          NOT NULL IDENTITY(1,1),
    --     [created_at] DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
    --     CONSTRAINT [PK_{{NAME}}] PRIMARY KEY ([id])
    -- );
    PRINT 'Migration {{NAME}} applied.';
END
ELSE
BEGIN
    PRINT 'Migration {{NAME}} already applied — skipped.';
END

COMMIT TRANSACTION;
