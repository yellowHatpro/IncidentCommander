import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

export function ErrorPanel({ message }: { message: string }) {
  return (
    <Card className="border-rose-500/30">
      <CardHeader>
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-rose-300">
          Backend Error
        </p>
        <CardTitle>Dashboard data could not be loaded.</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm leading-7 text-muted-foreground">{message}</p>
      </CardContent>
    </Card>
  );
}
