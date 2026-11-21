"""Fallback app used when the app phase fails: one searchable table per record type.

It is a kit app (v2) and passes the same checks as generated apps, so a build always ends
with something the user can look at (and fix by chat).
"""

# ruff: noqa: E501  (the embedded app is JSX, not Python)

DEFAULT_APP = r"""
<script type="text/jsx">
function App({ data }) {
  const names = types(data);
  if (!names.length) {
    return <EmptyState title="No records yet" description="New matching emails will appear here." />;
  }
  return (
    <Page>
      {names.map((t) => {
        const list = records(data, t);
        return (
          <Section key={t} title={fmt.label(t)} description={list.length + (list.length === 1 ? " record" : " records")}>
            <DataTable records={list} search />
          </Section>
        );
      })}
    </Page>
  );
}
</script>
"""
