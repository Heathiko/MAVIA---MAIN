import React, { useCallback, useState } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";
import { Redirect, Tabs, router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

import { useAuth } from "@/auth/AuthContext";
import { useNarration } from "@/hooks/useNarration";
import { hasHeardGuide, useGuideOnFirstLaunch } from "@/guide/useGuide";
import { GuideMenu } from "@/guide/GuideMenu";
import { useBrailleKeypad } from "@/input/useBrailleKeypad";
import { useVoiceCommands } from "@/voice/useVoiceCommands";
import { SwipeToCourses } from "@/nav/SwipeToCourses";
import { colors } from "@/theme";

type IconName = keyof typeof Ionicons.glyphMap;

// Matches the reference layout's bottom bar: a "library" tab (course list ->
// lesson list -> player, nested under home/) and a profile tab.
const TABS: { name: string; title: string; icon: IconName; iconOutline: IconName }[] = [
  { name: "home", title: "Home", icon: "home", iconOutline: "home-outline" },
  { name: "profile", title: "Profile", icon: "person-circle", iconOutline: "person-circle-outline" },
];

export default function StudentLayout() {
  const { user, loading } = useAuth();
  const narration = useNarration();
  const signedIn = Boolean(user) && user?.role === "STUDENT";

  // The guide plays itself the first time a learner ever gets here, and is on
  // the minus key and the "how does this work" commands forever after. It
  // lives at the layout rather than on a screen so that pressing minus works
  // wherever they are -- being lost is exactly when it is wanted.
  const guide = useGuideOnFirstLaunch(narration, { enabled: signedIn });
  const [menuOpen, setMenuOpen] = useState(false);

  // Minus means "help me" both times, but it should not mean the same eight
  // paragraphs twice. Never heard it: play the whole thing. Heard it: offer
  // the four sections and read only the one asked for.
  const openGuide = useCallback(() => {
    setMenuOpen(false);
    void hasHeardGuide().then((heard) => {
      if (heard) setMenuOpen(true);
      else guide.play();
    });
  }, [guide]);

  const goToCourses = useCallback(() => {
    guide.stop();
    narration.stop();
    router.push("/home");
  }, [guide, narration]);

  // Divide is "back" everywhere, and back means the nearest thing to leave --
  // not always a screen. Something talking at you is the thing you most want
  // out of, so it is unwound first: stop the guide, then close the menu, and
  // only then leave the screen. Without the ordering, pressing divide during
  // the guide would navigate while it kept talking over the new screen.
  const goBack = useCallback(() => {
    if (guide.playing) {
      guide.stop();
      return;
    }
    if (menuOpen) {
      setMenuOpen(false);
      narration.stop();
      return;
    }
    narration.stop();
    if (router.canGoBack()) router.back();
    else router.replace("/home");
  }, [guide, menuOpen, narration]);

  // App-wide keys. Answer keys are deliberately not handled here: they belong
  // to whichever screen is asking a question, and the keypad hook is
  // refcounted so both listeners can be live at once.
  useBrailleKeypad(
    (action) => {
      if (action.kind === "guide") openGuide();
      if (action.kind === "back") goBack();
    },
    { enabled: signedIn }
  );

  useVoiceCommands(
    {
      playGuide: () => openGuide(),
      goBack: () => goBack(),
    },
    { enabled: signedIn }
  );

  if (loading) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator color={colors.brand600} size="large" />
      </View>
    );
  }
  if (!user) {
    return <Redirect href="/login" />;
  }
  if (user.role !== "STUDENT") {
    return <Redirect href="/not-supported" />;
  }

  return (
    <SwipeToCourses onSwipe={goToCourses}>
      <View style={styles.fill}>
        <GuideMenu
          open={menuOpen}
          narration={narration}
          onPlaySection={guide.playSection}
          onClose={() => setMenuOpen(false)}
        />
        <Tabs
          screenOptions={{
            headerShown: false,
            tabBarActiveTintColor: colors.brand600,
            tabBarInactiveTintColor: colors.faint,
            tabBarStyle: styles.tabBar,
            tabBarLabelStyle: styles.tabLabel,
          }}
        >
          {TABS.map((tab) => (
            <Tabs.Screen
              key={tab.name}
              name={tab.name}
              options={{
                title: tab.title,
                tabBarIcon: ({ color, focused, size }) => (
                  <Ionicons name={focused ? tab.icon : tab.iconOutline} color={color} size={size} />
                ),
              }}
            />
          ))}
        </Tabs>
      </View>
    </SwipeToCourses>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  loading: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.page },
  tabBar: {
    borderTopColor: colors.border,
    height: 62,
    paddingBottom: 8,
    paddingTop: 6,
  },
  tabLabel: { fontSize: 11, fontWeight: "700" },
});
