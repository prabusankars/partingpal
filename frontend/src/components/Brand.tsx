import logo from "../assets/chat.png";

// App logo and name, shown in headers and on standalone cards.
export default function Brand({ as: Tag = "span" }: { as?: "span" | "h1" }) {
  return (
    <Tag className="brand">
      <img src={logo} alt="" className="brand-logo" />
      Parting Pal
    </Tag>
  );
}
