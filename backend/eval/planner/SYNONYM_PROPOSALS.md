# Synonym proposals (from the run 20261111T144452Z, rescored after the D6 fix)

Status: PROPOSED, not applied. `expected.yaml` is unchanged until Jihad approves.

## Synonyms (same concept, different name)
| Case | Record type | Label field | Add synonym |
|---|---|---|---|
| apartment-viewings | property | deposit | deposit_info |
| apartment-viewings | viewing | property | property_name |
| tenant-repair-requests | repair_request | description | issue_name |
| tool-subscriptions-renewals | subscription | renewal_date | next_renewal_date |
| tool-subscriptions-renewals | subscription | user | assigned_users |
| web-clients-projects-signoffs | approval | project | project_title |
| web-clients-projects-signoffs | approval | item | item_description |
| support-needs-reply | record type | customer_email | pending_support_thread |

## Optional fields (allowed, not counted as over-generation)
| Case | Record type | Add |
|---|---|---|
| tenant-repair-requests | repair_request | property_location, flat_location, flat_address |
| client-pipeline-board | client | project_description |
| tool-subscriptions-renewals | subscription | billing_frequency |

## Real misses (no label change)
property.status omitted (required by D1); supplier record type missing (vendor-invoices);
extra `user` record type (subscriptions); po_number marked found; extra plan_type.
