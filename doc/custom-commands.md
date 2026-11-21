# Custom commands

[Back to README](../README.md)

Keep your own Python commands in a folder of their own and add it:

```sh
mcp_sh_gimp commands add ~/code/gimp-tools
```

A `_lib.py` in that folder is appended to the built-in one, so your commands can use and
replace its helpers (`targets`, `resolve`, `layer_info`, `image_ref`, `convert`,
`undo_group`, `pdb_call`, ...). Check before changing anything and print last, as the
built-in commands do. See the core [script command reference](https://github.com/brohd11/mcp-sh/blob/main/doc/script-commands.md)
for help comments, `ARGS`/`STDIN`/`CWD`, libraries and folder precedence.
