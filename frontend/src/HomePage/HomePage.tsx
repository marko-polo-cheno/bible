import { Link } from 'react-router-dom';
import { Button, Container, Stack, Text, Title } from '@mantine/core';

function HomePage() {
  return (
    <Container size="sm" py={80}>
      <Stack align="center" gap="xl">
        <Stack align="center" gap={4}>
          <Title order={1} ta="center">
            Almonds &amp; Olives
          </Title>
          <Text c="dimmed" ta="center">
            Choose where you&apos;d like to go.
          </Text>
        </Stack>

        <Stack w="100%" maw={320} gap="md">
          <Button component={Link} to="/bible" size="xl" fullWidth>
            Bible
          </Button>
          <Button
            component={Link}
            to="/elibrary"
            size="xl"
            fullWidth
            variant="light"
          >
            eLibrary
          </Button>
        </Stack>
      </Stack>
    </Container>
  );
}

export default HomePage;
