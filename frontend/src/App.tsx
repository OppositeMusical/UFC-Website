import { Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import ScrollProgress from "./components/ScrollProgress";
import Home from "./pages/Home";
import Download from "./pages/Download";
import About from "./pages/About";
import Pricing from "./pages/Pricing";
import Login from "./pages/Login";
import Account from "./pages/Account";
import CheckoutSuccess from "./pages/CheckoutSuccess";
import "./styles/accounts.css";

export default function App() {
  return (
    <>
      <ScrollProgress />
      <Navbar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/download" element={<Download />} />
        <Route path="/about" element={<About />} />
        <Route path="/pricing" element={<Pricing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/account" element={<Account />} />
        {/* Stripe returns here on success; cancelling goes back to /pricing,
            which needs no route of its own. */}
        <Route path="/checkout/success" element={<CheckoutSuccess />} />
      </Routes>
      <Footer />
    </>
  );
}
