import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PageMessage } from './PageMessage'

describe('PageMessage', () => {
  it('uses alert semantics for errors and status semantics for success', () => {
    render(
      <>
        <PageMessage>保存に失敗しました</PageMessage>
        <PageMessage variant="success">保存しました</PageMessage>
      </>,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('保存に失敗しました')
    expect(screen.getByRole('status')).toHaveTextContent('保存しました')
  })
})
