export default function Footer() {
  return (
    <footer className="footer">
      <div className="container">
        <p>
          UFC Predictor is an independent, informational tool. It is not affiliated with the UFC, PrizePicks,
          DraftKings, or Kalshi, and it does not place bets or wagers on your behalf.
        </p>
        <p>&copy; {new Date().getFullYear()} UFC Predictor.</p>
      </div>
    </footer>
  );
}
