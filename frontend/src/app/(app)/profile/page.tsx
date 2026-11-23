/** `/profile`: edit first and last name, see the sign-in email, connect or switch Gmail. */
import type { Metadata } from "next";
import { PageTransition } from "@/components/motion/PageTransition";
import { ProfileScreen } from "@/components/profile/ProfileScreen";

export const metadata: Metadata = { title: "Profile" };

export default function ProfilePage() {
  return (
    <PageTransition>
      <ProfileScreen />
    </PageTransition>
  );
}
