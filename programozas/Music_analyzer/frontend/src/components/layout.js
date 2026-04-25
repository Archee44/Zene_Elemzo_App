import { AppShell, Text, ActionIcon, useMantineColorScheme, Menu } from "@mantine/core";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { IconSun, IconMoonStars } from "@tabler/icons-react";

export default function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { colorScheme, toggleColorScheme } = useMantineColorScheme();
  const dark = colorScheme === 'dark';

  const handleClick = (to) => {
    if (location.pathname === to) {
      navigate(0);
    }
  };

  return (
    <AppShell header={{ height: 80 }}
      style={{ backgroundImage: dark ? "url('/icons/dark_version.png')" : "url('/icons/light_version.jpg')", backgroundSize: "cover", backgroundPosition: "center",
      backgroundRepeat: "no-repeat", backgroundAttachment: "fixed",  minHeight: "100vh", color: dark ? "#fff" : "#000"}}>
      <AppShell.Header
        style={{ boxShadow: "0px 5px 10px 0px rgba(82, 63, 105, 0.05)", backgroundColor: dark ? "#0C1A2A" : "#FFF8E7" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", height: "100%", padding: "0 20px"}}>
            <Menu trigger="hover" openDelay={100} closeDelay={400} transitionProps={{ transition: "pop", duration: 150 }}>
                <Menu.Target>
                  <div
                    style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer", padding: "6px 12px", borderRadius: 8, transition: "background-color 0.2s" }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = dark ? "#1B2B4A" : "#FFF2CC")}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}>
                    <img src="/icons/New_MeloDive.png" alt="Logo" style={{ height: 50 }}/>
                    <Text style={{ fontSize: 30, fontWeight: "bold", color: dark ? "#fff" : "#0C1A2A", transition: "color 0.2s"}}>
                      MeloDive
                    </Text>
                  </div>
                </Menu.Target>
              <Menu.Dropdown
                style={{ backgroundColor: dark ? "#0C1A2A" : "#FFF8E7", border: `2px solid ${dark ? "#483d8b" : "#FFD966"}`, borderRadius: 12,
                boxShadow: "0 6px 20px rgba(0, 0, 0, 0.3)", padding: 15, minWidth: 280, transform: "scale(1.05)", zIndex: 1000 }}>
                <Menu.Item component={Link} to="/" onClick={() => handleClick("/")}
                    style={{ fontWeight: 600, fontSize: 18, padding: "14px 20px", color: dark ? "#FFFFFF" : "#0C1A2A", borderRadius: 8, transition: "all 0.25s ease" }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = dark ? "#483d8b" : "#FFD966")}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}> Főoldal </Menu.Item>
                <Menu.Item component={Link} to="/music-analyzer" onClick={() => handleClick("/music-analyzer")}
                    style={{ fontWeight: 600, fontSize: 18, padding: "14px 20px", color: dark ? "#FFFFFF" : "#0C1A2A", borderRadius: 8, transition: "all 0.25s ease" }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = dark ? "#483d8b" : "#FFD966")}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}> Zeneelemző </Menu.Item>
                <Menu.Item component={Link} to="/music-recommender" onClick={() => handleClick("/music-recommender")}
                    style={{ fontWeight: 600, fontSize: 18, padding: "14px 20px", color: dark ? "#FFFFFF" : "#0C1A2A", borderRadius: 8, transition: "all 0.25s ease" }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = dark ? "#483d8b" : "#FFD966")}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}> Zeneajánló </Menu.Item>
                <Menu.Item component={Link} to="/spotify-login" onClick={() => handleClick("/spotify-login")}
                    style={{ fontWeight: 600, fontSize: 18, padding: "14px 20px", color: dark ? "#FFFFFF" : "#0C1A2A", borderRadius: 8, transition: "all 0.25s ease" }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = dark ? "#483d8b" : "#FFD966") }
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent") }> Playlist elemző </Menu.Item>
                <Menu.Item component={Link} to="/search" onClick={() => handleClick("/search")}
                    style={{ fontWeight: 600, fontSize: 18, padding: "14px 20px", color: dark ? "#FFFFFF" : "#0C1A2A", borderRadius: 8, transition: "all 0.25s ease" }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = dark ? "#483d8b" : "#FFD966") }
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent") }> Kereső </Menu.Item>
              </Menu.Dropdown>
            </Menu>
            <ActionIcon onClick={toggleColorScheme} variant="light" size="lg" radius="xl" title="Téma váltása"> {dark ? <IconSun size={20} /> : <IconMoonStars size={20} />}</ActionIcon>
          </div>
      </AppShell.Header>
      <AppShell.Main style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "calc(100vh - 80px)", paddingTop: 70 }}>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}

