export default function Footer() {
  return (
    <footer className="footer">
      <div className="container">
        <p>
          MMA Assist is an independent, informational tool. It is not affiliated with the UFC, PrizePicks,
          DraftKings, or Kalshi, and it does not place bets or wagers on your behalf.
        </p>
        <p>&copy; {new Date().getFullYear()} MMA Assist.</p>
      </div>
    </footer>
  );
}
