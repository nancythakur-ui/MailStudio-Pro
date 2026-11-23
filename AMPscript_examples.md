# AMPscript-style personalization reference

The local Flask preview uses Jinja variables (`{{name}}`) so it can run without a Salesforce account. Salesforce Marketing Cloud uses AMPscript, for example:

```ampscript
%%[
VAR @firstName
SET @firstName = AttributeValue("FirstName")
IF Empty(@firstName) THEN
  SET @firstName = "there"
ENDIF
]%%
Hello %%=v(@firstName)=%%,
```

This is a learning/reference example, not executable in this local app. Server-side JavaScript in Marketing Cloud is a platform-specific capability and should be tested in an authorized SFMC account.
