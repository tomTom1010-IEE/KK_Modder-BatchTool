# Interface localization

English is the source language for panels, buttons, properties, enum labels,
tooltips, status messages, and errors. Blender's interface language controls
the translated display; Simplified Chinese is maintained alongside English.

- `kk_vrc_cloth_tools/translations.py`: Blender translation registration and
  the legacy English-to-Chinese catalog.
- `kk_vrc_cloth_tools/ui_messages.py`: new English/Chinese messages and formatted
  templates. `format_message()` translates a template before substituting values.
- `tests/test_localization_blender.py`: factory-startup Blender checks for panel
  registration, both languages, template placeholders, and preserved identifiers.

Keep new source labels in English and add a corresponding Chinese catalog entry.
Use complete templates for dynamic messages, rather than translating a formatted
result containing object names or counts. Do not translate bone names, object
identifiers, configuration keys, enum identifiers, or user-entered text.

Run the UI check with Blender in background factory-startup mode:

```text
blender --background --factory-startup --python tests/test_localization_blender.py
```

Switch Blender to English or Simplified Chinese under Preferences → Interface →
Translation. Enable Interface translation for Chinese labels. Changing language
does not modify stored bone mappings, weights, or user-entered names. Existing
saved status text or user-named poses are retained; new operations generate new
messages using the current code.
