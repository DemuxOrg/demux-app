/** `/` has no page of its own: signed-in users land on their workspaces (proxy.ts sends
 * everyone else to /login). */
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/workspaces");
}
