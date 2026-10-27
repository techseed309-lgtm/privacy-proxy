# Before you trust a privacy proxy (or any "we hide your data" tool)

1. **Test on fake documents first.** Never use real people's details to find out whether a tool works.
2. **Make an answer key.** For every test document, list every personal value in it, so leaks can be counted, not
   guessed.
3. **Use a strict leak rule.** Any readable part counts: a surname alone, digits with different spacing, half a
   postcode, the last four digits of a card.
4. **Score on a pile the tool has never seen.** Every time you change a rule, generate a fresh pile and test on that.
5. **Look for the second mention.** Titles + surnames ("Dr Price"), first names in sign-offs, initials, names in email
   addresses, names in form fields.
6. **Look for fragments.** "Card ending 1234", partial account numbers, a date of birth next to a town.
7. **Check what was actually sent.** Log the exact text that left your machine, and read some of it yourself.
8. **Check the answer comes back.** Count tags restored, tags the model changed, and tags it invented.
9. **Check one person = one tag.** If a person gets two tags, the answer can treat them as two people.
10. **Protect the list.** The tag → real value list is now the most sensitive file you have. Keep it local, delete it
    when you're done.
11. **Remember what masking can't do.** A rare job title in a small town can identify someone with no name at all.
12. **Consider the stronger options:** don't paste it, use a model that runs on your own machine, and check the
    chatbot's data settings.
